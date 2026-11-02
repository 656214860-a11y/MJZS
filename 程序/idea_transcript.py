# -*- coding: utf-8 -*-
"""创意对话的聊天记录持久化：对话行的读取、追加、改写、删除与恢复。

从 L2 ``idea_chat`` 拆出（R1319 结构治理轮）：``load``／``append``／``replace``／
``remove``／``remove_all``／``restore_latest_removed``／``compact_context``／
``repair_internal_replies`` 及其私有读写辅助（``_all_rows``／``_read_rows``／
``save_rows``／``_row_indexes``／``_stamp``／``_visible_claude_text``，模型会话路径
``folder``／``history_path``／``chat_model``／``model_history_path``／
``deleted_history_path``）。函数签名、返回结构与缓存上限原值不变。

只做对话记录的读写与迁移，不碰 Tk、不发网络；正式读写仍须由 L3 注入网关
（``read_json``／``publish_json``／``publish_text``／``recycle_paths``）。
``_context`` 沿用本项目各 L2 模块各自持有 ProjectContext 校验的惯例，在本模块内
保留独立一份。
"""
import ast
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from project_context import ProjectContext
from idea_document_paths import ChatModel, _storage_name, storage_identity


FOLDER = '创意对话'
CHAT_NAME = '对话.json'
_HISTORY_CACHE_LIMIT = 16
_history_cache = OrderedDict()


def _context(value):
    if not isinstance(value, ProjectContext):
        raise TypeError('创意聊天项目路径需要由 L3 注入 ProjectContext。')
    return value


def _require_gateway(gateway):
    """创意聊天的正式读写只能由 L3 注入，避免 L2 自行落盘。"""
    required = ('read_json', 'publish_json', 'publish_text')
    if not isinstance(gateway, dict) or any(not callable(gateway.get(name)) for name in required):
        raise TypeError('创意聊天读写需要由 L3 注入发布与读取网关。')
    return gateway


def folder(context):
    from project_stages import writing
    return writing(_context(context).root) / FOLDER


def history_path(root):
    """旧版统一聊天记录位置；只作为一次性兼容导入源。"""
    return folder(root) / CHAT_NAME


def chat_model(model):
    if isinstance(model, ChatModel):
        return model
    import model_pool
    shown = str(model or '').strip()
    records = model_pool.pool(program=Path(__file__).resolve().parent)
    matches = [key for key, record in records.items() if record.get('label') == shown]
    key = shown if shown in records else (matches[0] if len(matches) == 1 else '')
    if len(matches) > 1 and not key:
        raise ValueError('模型显示名重复，请通过模型 ID 选择会话')
    record = records.get(key, {})
    return ChatModel(str(record.get('label') or shown), key,
                     model_pool.provider_name(key, record) if key else '')


def model_history_path(context, model, provider=''):
    """当前模型的唯一聊天记录位置：不再混放在剧本准备根目录。"""
    identity = chat_model(model) if not provider else ChatModel(str(model))
    if identity.model_id and not provider:
        import hashlib
        provider_name = '模型会话'
        model_name = (_storage_name(identity.model_id, '模型') + '--' +
                      hashlib.sha256(identity.model_id.encode('utf-8')).hexdigest()[:12])
    else:
        provider_name, model_name = (storage_identity(model) if not provider else
                                 (_storage_name(provider, '未知Provider'),
                                  _storage_name(model, '未知模型')))
    from project_stages import writing
    return writing(_context(context).root) / provider_name / model_name / FOLDER / CHAT_NAME


def deleted_history_path(root, model=None, provider=''):
    """对话页的可恢复删除记录；与对应模型的会话文件放在同一位置。"""
    path = (model_history_path(root, model, provider=provider)
            if str(model or '').strip() else history_path(root))
    return path.with_name('已删除消息.json')


def _stamp(at=None):
    moment = datetime.fromtimestamp(at) if at is not None else datetime.now()
    return moment.strftime('%Y%m%d_%H%M%S_%f')


def _read_rows(path, gateway):
    """读取单个历史文件；以 mtime/大小失效的内存缓存避免重复 JSON 解析。"""
    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        _history_cache.pop(path, None)
        return []
    fingerprint = (stat.st_mtime_ns, stat.st_size)
    cached = _history_cache.get(path)
    if cached and cached[0] == fingerprint:
        _history_cache.move_to_end(path)
        return [dict(row) for row in cached[1]]
    try:
        data = gateway['read_json'](path)
    except (OSError, ValueError):
        return []
    rows = data.get('messages') if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    rows = [dict(row) for row in rows if isinstance(row, dict) and str(row.get('text') or '').strip()]
    _history_cache[path] = (fingerprint, tuple(rows))
    _history_cache.move_to_end(path)
    while len(_history_cache) > _HISTORY_CACHE_LIMIT:
        _history_cache.popitem(last=False)
    return [dict(row) for row in rows]


def _all_rows(root, model=None, provider='', *, gateway=None):
    """读取聊天记录；指定模型时优先 Provider/模型目录并兼容导入旧统一记录。"""
    gateway = _require_gateway(gateway)
    key = str(model or '').strip()
    if not key:
        rows = _read_rows(history_path(root), gateway)
        from project_stages import writing
        base = writing(_context(root).root)
        if base.is_dir():
            for path in base.glob('*/*/' + FOLDER + '/' + CHAT_NAME):
                if path == history_path(root):
                    continue
                rows.extend(_read_rows(path, gateway))
        # 兼容导入期间旧统一文件和新模型文件可能短暂都含同一行；按完整记录
        # 去重，避免聊天框把一条消息显示两次。
        unique = []
        fingerprints = set()
        for row in rows:
            fingerprint = json.dumps(row, ensure_ascii=False, sort_keys=True)
            if fingerprint not in fingerprints:
                fingerprints.add(fingerprint)
                unique.append(row)
        return unique
    identity = chat_model(model)
    current = model_history_path(root, identity, provider=provider)
    legacy_labels = {key, str(identity)}
    # 旧显示名目录只作一次性迁移源。先发布新副本，再清空旧记录；失败可重试。
    if identity.model_id and not provider:
        import model_pool
        records = model_pool.pool(program=Path(__file__).resolve().parent)
        locations = records.get(identity.model_id, {}).get('history_locations', [])
        legacy_labels.update(entry['label'] for entry in locations)
        old_paths = [model_history_path(root, str(identity), provider=identity.provider or '未知Provider')]
        old_paths.extend(model_history_path(root, entry['label'], provider=entry['provider']) for entry in locations)
        migration_paths = [(old, current) for old in dict.fromkeys(old_paths)]
        migration_paths.extend((old.with_name('已删除消息.json'), current.with_name('已删除消息.json'))
                               for old in dict.fromkeys(old_paths))
        for source, target in migration_paths:
            legacy = gateway['read_json'](source) if source.is_file() else {}
            legacy_rows = legacy.get('messages', []) if isinstance(legacy, dict) else []
            legacy_rows = [row for row in legacy_rows if isinstance(row, dict)]
            if legacy_rows and source != target:
                owners = set()
                for model_id, record in records.items():
                    candidates = [{'label': record.get('label') or model_id,
                                   'provider': model_pool.provider_name(model_id, record)}]
                    candidates.extend(record.get('history_locations') or [])
                    if any(model_history_path(root, entry['label'], provider=entry['provider']).parent == source.parent
                           for entry in candidates):
                        owners.add(model_id)
                if owners - {identity.model_id}:
                    raise ValueError('旧历史目录对应多个模型，无法确定归属；原记录已保留，请先核对模型身份。')
                existing = gateway['read_json'](target) if target.is_file() else {}
                migrated = list(existing.get('messages', [])) if isinstance(existing, dict) else []
                for row in legacy_rows:
                    item = dict(row, model_id=identity.model_id)
                    if isinstance(item.get('row'), dict):
                        item['row'] = dict(item['row'], model_id=identity.model_id)
                    if item not in migrated:
                        migrated.append(item)
                gateway['publish_json'](target, {'version': 2, 'model_id': identity.model_id, 'messages': migrated})
                gateway['publish_json'](source, {'version': 2, 'migrated_to': str(target.relative_to(_context(root).root)), 'messages': []})
    rows = _read_rows(current, gateway)
    if rows or current.exists():
        return rows
    # 历史版本把所有模型写进一份根目录 JSON；首次切到模型页时只导入它自己的
    # 记录，避免不同 Provider 的聊天页再度串线。
    legacy = _read_rows(history_path(root), gateway)
    selected = [row for row in legacy if (row.get('model_id') == identity.model_id
                if row.get('model_id') and identity.model_id else str(row.get('model') or '') in legacy_labels)]
    if not selected and legacy and not any(str(row.get('model') or '').strip() for row in legacy):
        selected = legacy
    if selected:
        # 导入是迁移而不是复制：保留未属于当前模型的旧记录，移除已迁入部分，
        # 防止无模型读取时重新显示已删除／已编辑的旧副本。
        selected_fingerprints = {json.dumps(row, ensure_ascii=False, sort_keys=True) for row in selected}
        remaining = [row for row in legacy
                     if json.dumps(row, ensure_ascii=False, sort_keys=True) not in selected_fingerprints]
        save_rows(root, selected, model=identity, provider=provider, gateway=gateway)
        if remaining != legacy:
            save_rows(root, remaining, gateway=gateway)
    return selected


def load(root, model=None, *, gateway=None):
    """读取对话；指定模型时只返回该模型自己的聊天页。"""
    rows = _all_rows(root, model=model, gateway=gateway)
    key = str(model or '').strip()
    if not key:
        return rows
    selected = [rows[index] for index in _row_indexes(rows, model)]
    if selected:
        return selected
    # 旧版本的对话没有 model 字段。仅当整个文件都是这种旧格式时才展示它，
    # 防止已分区的新对话在切换模型后串到另一个聊天页。
    if rows and not any(str(row.get('model') or '').strip() for row in rows):
        return rows
    return []


def append(root, role, text, at=None, model=None, *, gateway=None, context_budget=None, request_usage=None, skill_injection=None):
    """记一轮对话（读回来再追加，原子写：写坏一次不会把整段对话丢掉）。"""
    rows = _all_rows(root, model=model, gateway=gateway)
    row = {'role': str(role), 'text': str(text), 'at': _stamp(at)}
    if isinstance(context_budget, dict):row['context_budget'] = dict(context_budget)
    if isinstance(request_usage, dict):row['request_usage'] = dict(request_usage)
    if isinstance(skill_injection, dict):
        from copy import deepcopy
        row['skill_injection'] = deepcopy(skill_injection)
    if str(model or '').strip():
        identity = chat_model(model)
        row['model'] = str(identity)
        if identity.model_id:row['model_id'] = identity.model_id
    rows.append(row)
    return save_rows(root, rows, model=model, gateway=gateway)


def compact_context(root, model=None, *, gateway=None):
    """标记当前聊天为摘录输入；原文保留，后续新增消息仍正常进入上下文。"""
    rows = (_all_rows(root, model=model, gateway=gateway) if str(model or '').strip()
            else _read_rows(history_path(root), _require_gateway(gateway)))
    indexes = _row_indexes(rows, model)
    changed = False
    for index in indexes:
        if rows[index].get('context_compacted') is not True:
            rows[index]['context_compacted'] = True
            changed = True
    if changed:
        save_rows(root, rows, model=model, gateway=gateway)
    return load(root, model=model, gateway=gateway)


def _visible_claude_text(value):
    """从历史中误存的 Claude 内容块取回正文，不把 thinking／signature 展示给用户。"""
    raw = str(value or '').strip()
    if not raw or raw[0] not in '[{':
        return raw, False
    try:
        decoded = ast.literal_eval(raw)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return raw, False
    blocks = decoded.get('content') if isinstance(decoded, dict) else decoded
    if not isinstance(blocks, (list, tuple)):
        return raw, False
    internal = False
    visible = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = str(block.get('type') or '')
        if kind in ('thinking', 'tool_use', 'tool_result') or 'signature' in block:
            internal = True
        if kind in ('text', 'output_text') and str(block.get('text') or '').strip():
            visible.append(str(block['text']).strip())
    return '\n'.join(visible), internal


def repair_internal_replies(root, model=None, *, gateway=None):
    """清理历史中的 Claude 内部块，并返回最后一条可安全补发的用户创意。"""
    rows = _all_rows(root, model=model, gateway=gateway)
    key = str(model or '').strip()
    selected = set(_row_indexes(rows, model))
    repaired = []
    changed = False
    latest_user = ''
    retry_creative = ''
    for index, row in enumerate(rows):
        item = dict(row)
        if key and index not in selected:
            repaired.append(item)
            continue
        if str(item.get('role')) == 'user':
            latest_user = str(item.get('text') or '').strip()
            repaired.append(item)
            continue
        text, internal = _visible_claude_text(item.get('text'))
        if not internal:
            repaired.append(item)
            continue
        changed = True
        if text:
            item['text'] = text
            repaired.append(item)
        elif latest_user:
            # 只有思考块时不能伪造正文：移除乱码，再由界面按用户明确点击“刷新”补发一次。
            retry_creative = latest_user
    if changed:
        save_rows(root, repaired, model=model, gateway=gateway)
    return {'changed': changed, 'retry_creative': retry_creative}


def save_rows(root, rows, model=None, provider='', *, gateway=None):
    """原子保存完整对话；编辑、删除和追加共用这一条落盘路径。"""
    gateway = _require_gateway(gateway)
    identity = chat_model(model) if str(model or '').strip() else None
    if identity is not None and identity.model_id:
        rows = [dict(row, model_id=identity.model_id)
                if not row.get('model_id') and str(row.get('model') or '') in ('', str(identity), identity.model_id)
                else dict(row) for row in rows]
    path = model_history_path(root, model, provider=provider) if str(model or '').strip() else history_path(root)
    gateway['publish_json'](path, {'version': 1, 'messages': rows})
    try:
        stat = path.stat()
        clean = tuple(dict(row) for row in rows if isinstance(row, dict) and str(row.get('text') or '').strip())
        _history_cache[path] = ((stat.st_mtime_ns, stat.st_size), clean)
        _history_cache.move_to_end(path)
        while len(_history_cache) > _HISTORY_CACHE_LIMIT:
            _history_cache.popitem(last=False)
    except OSError:
        _history_cache.pop(path, None)
    return rows


def _row_indexes(rows, model=None):
    key = str(model or '').strip()
    if not key:
        return list(range(len(rows)))
    identity = chat_model(model)
    selected = [index for index, row in enumerate(rows)
                if ((row.get('model_id') == identity.model_id) if row.get('model_id') and identity.model_id
                    else str(row.get('model') or '').strip() in (key, str(identity)))]
    if selected:
        return selected
    if rows and not any(str(row.get('model') or '').strip() for row in rows):
        return list(range(len(rows)))
    return []


def replace(root, index, text, model=None, *, gateway=None):
    """修改指定消息，不允许把对话改成空白。"""
    rows = _all_rows(root, model=model, gateway=gateway)
    indexes = _row_indexes(rows, model)
    if not isinstance(index, int) or not 0 <= index < len(indexes):
        raise ValueError('这条对话已不存在，请刷新后重试')
    value = str(text or '').strip()
    if not value:
        raise ValueError('对话内容不能为空')
    rows[indexes[index]]['text'] = value
    rows[indexes[index]].pop('context_compacted', None)
    return save_rows(root, rows, model=model, gateway=gateway)


def remove(root, index, model=None, *, gateway=None):
    """移除指定消息，并保留可恢复记录；调用方负责向用户确认。"""
    gateway = _require_gateway(gateway)
    rows = _all_rows(root, model=model, gateway=gateway)
    indexes = _row_indexes(rows, model)
    if not isinstance(index, int) or not 0 <= index < len(indexes):
        raise ValueError('这条对话已不存在，请刷新后重试')
    original_index = indexes[index]
    removed = rows.pop(original_index)
    trash = deleted_history_path(root, model=model)
    try:
        history = gateway['read_json'](trash) if trash.is_file() else {}
    except (OSError, ValueError):
        history = {}
    records = history.get('messages') if isinstance(history, dict) else []
    records = records if isinstance(records, list) else []
    records.append({'row': removed, 'index': original_index,
                    'model': str(model or '').strip(), 'model_id': chat_model(model).model_id, 'deleted_at': _stamp()})
    gateway['publish_json'](trash, {'version': 1, 'messages': records[-100:]})
    saved = save_rows(root, rows, model=model, gateway=gateway)
    _purge_copies(root, removed, keep=model_history_path(root, model), gateway=gateway)
    return saved


def _chat_files(root):
    """项目里所有聊天记录文件：旧版统一文件＋各 Provider／模型目录（含旧版改名残留）。"""
    from project_stages import writing
    base = writing(_context(root).root)
    paths = [history_path(root)]
    if base.is_dir():
        paths.extend(base.glob('*/*/' + FOLDER + '/' + CHAT_NAME))
    return [path for path in dict.fromkeys(Path(item) for item in paths) if path.is_file()]


def remove_message(root, row, *, gateway=None):
    """按整条内容删除一条消息：项目内所有聊天文件里的相同副本一并移除，并记入该模型的最近删除。

    气泡框「全部」与按模型视图都按合并后的记录显示，消息可能落在旧版目录里；按单个
    模型文件的下标删除会删不到或只删掉其中一份。返回移除的副本数，没有找到时报错。
    """
    gateway = _require_gateway(gateway)
    if not isinstance(row, dict):
        raise ValueError('这条对话已不存在，请刷新后重试')
    removed = 0
    for path in _chat_files(root):
        try:
            data = gateway['read_json'](path)
        except (OSError, ValueError):
            continue
        rows = data.get('messages') if isinstance(data, dict) else data
        if not isinstance(rows, list):
            continue
        left = [item for item in rows if not (isinstance(item, dict) and _same_message(item, row))]
        if len(left) == len(rows):
            continue
        removed += len(rows) - len(left)
        payload = dict(data, messages=left) if isinstance(data, dict) else {'version': 1, 'messages': left}
        gateway['publish_json'](path, payload)
        _history_cache.pop(path, None)
    if not removed:
        raise ValueError('这条对话已不存在，请刷新后重试')
    model = str(row.get('model') or '').strip()
    trash = deleted_history_path(root, model=model or None)
    try:
        history = gateway['read_json'](trash) if trash.is_file() else {}
    except (OSError, ValueError):
        history = {}
    records = history.get('messages') if isinstance(history, dict) else []
    records = records if isinstance(records, list) else []
    records.append({'row': dict(row), 'index': 0, 'model': model,
                    'model_id': chat_model(model).model_id if model else '', 'deleted_at': _stamp()})
    gateway['publish_json'](trash, {'version': 1, 'messages': records[-100:]})
    return removed


def _same_message(left, right):
    """同一条消息的不同副本：忽略落盘时补写的 ``model_id``。"""
    return ({k: v for k, v in left.items() if k != 'model_id'}
            == {k: v for k, v in right.items() if k != 'model_id'})


def _purge_copies(root, removed, *, keep, gateway):
    """旧版目录改名／迁移会让同一条消息在项目里留下多份副本；
    「全部」视图把它们合并显示，只删一份会让这条消息从别的副本里重新冒出来。
    这里把除已处理文件外的其余聊天文件里相同的整条消息一并移除。"""
    from project_stages import writing
    base = writing(_context(root).root)
    paths = [history_path(root)]
    if base.is_dir():
        paths.extend(base.glob('*/*/' + FOLDER + '/' + CHAT_NAME))
    for path in dict.fromkeys(Path(item) for item in paths):
        if path == Path(keep) or not path.is_file():
            continue
        try:
            data = gateway['read_json'](path)
        except (OSError, ValueError):
            continue
        rows = data.get('messages') if isinstance(data, dict) else data
        if not isinstance(rows, list):
            continue
        left = [row for row in rows if not (isinstance(row, dict) and _same_message(row, removed))]
        if len(left) == len(rows):
            continue
        payload = dict(data, messages=left) if isinstance(data, dict) else {'version': 1, 'messages': left}
        gateway['publish_json'](path, payload)
        _history_cache.pop(path, None)


def remove_all(root, model, *, gateway=None):
    """回收当前模型的全部历史及单条恢复记录，保留其他模型与创作文件。"""
    gateway = _require_gateway(gateway)
    if not str(model or '').strip():
        raise ValueError('请先选择聊天模型')
    recycle = gateway.get('recycle_paths')
    if not callable(recycle):
        raise TypeError('删除全部信息需要 L3 注入回收入口')
    rows = load(root, model=model, gateway=gateway)
    legacy_path = history_path(root)
    legacy = _read_rows(legacy_path, gateway)
    selected = set(_row_indexes(legacy, model))
    remaining = [row for index, row in enumerate(legacy) if index not in selected]
    paths = [model_history_path(root, model), deleted_history_path(root, model=model)]
    if selected:
        paths.append(legacy_path)
    paths = [path for path in paths if path.is_file()]
    if paths:
        try:
            recycle(_context(root).root, paths, '删除全部聊天信息')
            if any(path.exists() for path in paths):
                raise OSError('部分聊天记录未能移入回收站，请重试')
        finally:
            if selected and remaining and not legacy_path.exists():
                save_rows(root, remaining, gateway=gateway)
    return len(rows) + _strip_model_rows(root, model, gateway=gateway)


def _strip_model_rows(root, model, *, gateway):
    """旧版目录改名残留里署名为该模型的记录也属于它的标签视图；一并移除，
    否则清空后标签仍在、记录从残留文件里重新显示。返回移除条数。"""
    label = str(model or '').strip()
    removed = 0
    for path in _chat_files(root):
        try:
            data = gateway['read_json'](path)
        except (OSError, ValueError):
            continue
        rows = data.get('messages') if isinstance(data, dict) else data
        if not isinstance(rows, list):
            continue
        left = [row for row in rows if not (isinstance(row, dict) and str(row.get('model') or '').strip() == label)]
        if len(left) == len(rows):
            continue
        removed += len(rows) - len(left)
        payload = dict(data, messages=left) if isinstance(data, dict) else {'version': 1, 'messages': left}
        gateway['publish_json'](path, payload)
        _history_cache.pop(path, None)
    return removed


def restore_latest_removed(root, model=None, *, gateway=None):
    """恢复当前会话最近删除的一条消息，其他模型的删除记录不相互串入。"""
    gateway = _require_gateway(gateway)
    _all_rows(root, model=model, gateway=gateway)
    trash = deleted_history_path(root, model=model)
    try:
        history = gateway['read_json'](trash) if trash.is_file() else {}
    except (OSError, ValueError) as exc:
        raise ValueError('没有可恢复的对话删除记录') from exc
    records = history.get('messages') if isinstance(history, dict) else []
    key = str(model or '').strip()
    if not isinstance(records, list):
        records = []
    identity = chat_model(model)
    choices = [i for i, record in enumerate(records)
               if isinstance(record, dict) and ((record.get('model_id') == identity.model_id)
                   if record.get('model_id') and identity.model_id else str(record.get('model') or '') == key)
               and isinstance(record.get('row'), dict)]
    if not choices:
        raise ValueError('没有可恢复的对话删除记录')
    record = records.pop(choices[-1])
    rows = _all_rows(root, model=model, gateway=gateway)
    position = min(max(0, int(record.get('index', len(rows)))), len(rows))
    rows.insert(position, record['row'])
    gateway['publish_json'](trash, {'version': 1, 'messages': records})
    save_rows(root, rows, model=model, gateway=gateway)
    return record['row']
