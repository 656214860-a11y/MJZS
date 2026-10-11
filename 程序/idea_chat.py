# -*- coding: utf-8 -*-
"""创意对话：剧本准备页的创意栏改成跟模型对话的那一扇窗。

用户原话：「把创意内容栏改为打开 agent 后与 LLM 的对话框；保存创意按钮改为提交创意，
本地再保存提交创意的文件，通过 agent 与 LLM 对话，只保存 LLM 输出文本」。

落地口径（三件事各自只有一个归属）：
- 整段对话按轮次记在 writing/创意对话/对话.json（界面重建后照样看得见，翻页不丢）；
- **只有模型的输出**落成下游读的那个创意文件：writing/<Provider>/<模型名>/创意_<日期>/<项目>_<集数>_<日期>.md
  （用户确认下载后才写入；每个 Provider 和模型各自保留目录）。

这一份只做文件与人话：不碰 Tk、不发网络。问模型那一趟由界面注入（自检传假函数），离线可跑。
"""
import ast
import json
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from idea_script_heuristic import looks_like_script
from project_context import ProjectContext
from script_contract import INLINE_REQUIRED_LABELS, PRODUCTION_LOCK_DEFINITIONS, stage_lock_requirements, stage_lock_definitions
from idea_document_paths import (
    PROJECT_DOCUMENT_DIRS, ChatModel, project_document_directory, project_script_filename,
    reply_document_path, reply_path_parts, storage_identity, _file_day, _project_file_type, _storage_name)

FOLDER = '创意对话'
CHAT_NAME = '对话.json'
# ``brief_creation.md`` is the one user-facing source of truth for a creation
# brief.  ``brief_raw.md`` remains read-only compatibility input for projects
# made before the intake form existed.
BRIEF_CREATION_NAME = 'brief_creation.md'
LEGACY_BRIEF_RAW_NAME = 'brief_raw.md'
BRIEF_RAW_NAME = BRIEF_CREATION_NAME
RAW_SCRIPT_NAME = 'script_raw.md'
BRIEF_COMPLETE_NAME = 'brief_complete.json'
REPLY_LIMIT = 20000          # 一次回复最多留这么多字：模型跑飞时不至于把文件写爆
PROJECT_CONTENT_MARKS = ('项目设定', '人物设定', '世界观', '需求梳理', '项目大纲', '大纲', '纲要', '分集', '剧本', '场景', '镜头', '台词')
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


def brief_raw_path(context):
    """HOLLMWOOD 的原始用户简报（唯一文件：brief_creation.md）。"""
    from project_stages import writing
    return writing(_context(context).root) / BRIEF_RAW_NAME


def legacy_brief_raw_path(context):
    """旧项目的简报位置；仅在新文件尚未创建时导入读取。"""
    from project_stages import writing
    return writing(_context(context).root) / LEGACY_BRIEF_RAW_NAME


def brief_complete_path(context):
    """经完整性检查后才会出现的 HOLLMWOOD 输入文件。"""
    from project_stages import writing
    return writing(_context(context).root) / BRIEF_COMPLETE_NAME


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


def skill_injection_summary(row):
    """请求记录显示已勾选与实际加载；不把历史记录伪装成有加载凭据。"""
    snapshot = row.get('skill_injection')
    if not isinstance(snapshot, dict):
        return ''
    selected = snapshot.get('selected') or []
    loaded = snapshot.get('loaded') or []
    names = '、'.join(str(item.get('name') or '') for item in loaded)
    return f"SKILL：已勾选 {len(selected)} 项，本次已加载 {len(loaded)} 项" + ('（' + names + '）' if names else '')


def usage_summary(rows):
    """仅概述当前模型最近一次已保存回复；缺报不能伪装成零消耗。"""
    row = next((row for row in reversed(rows) if row.get('role') == 'assistant'), {})
    budget, usage = row.get('context_budget') or {}, row.get('request_usage') or {}
    if not budget and not usage:
        return '本模型暂无用量记录'
    def shown(value):
        return str(value) if value is not None else '未提供'
    return ('上次请求：输入估算 ' + shown(budget.get('input_tokens')) + ' token / 容量 '
            + shown(budget.get('context_limit')) + '；输出预留 ' + shown(budget.get('output_reserved'))
            + '；API 实报输入/输出/缓存：' + '/'.join(shown(usage.get(key)) for key in
                ('prompt_tokens', 'completion_tokens', 'cached_tokens')))


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
    return save_rows(root, rows, model=model, gateway=gateway)


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
    return len(rows)


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


def save_reply(root, text, at=None, provider='', model='', *, publish=None):
    """组织确认下载的模型创意；发布由调用方注入的 L3 完成。"""
    context = _context(root)
    value = str(text or '').replace('\r\n', '\n').strip()
    if not value:
        raise ValueError('模型没有输出文字，未写入创意文件')
    if not is_project_document_text(value):
        raise ValueError('模型回复不是项目设定、大纲或剧本，未写入项目文件')
    if not callable(publish):
        raise TypeError('模型创意文件需要由 L3 注入发布器。')
    file_type = _project_file_type(value)
    if file_type == '自然剧本':
        from script_contract import require_natural_script
        value = require_natural_script(value)
    from stage_path_service import write_dir
    path = reply_document_path(context, value, at=at, provider=provider, model=model, file_type=file_type)
    # 正文与既有文件一致才复用；审阅参考稿（设定／大纲／角色卡）正文变了要覆盖写入。
    if path.is_file() and path.read_text(encoding='utf-8', errors='ignore').strip() == value:
        return path
    parts = path.relative_to(write_dir(context.root, 'script')).parts
    folder = '/'.join(parts[:-2])
    name = '/'.join(parts)
    return publish(context.root, ({'name': name, 'data': value.encode('utf-8'),
                           'directories': tuple(folder + '/' + directory
                                                for directory in PROJECT_DOCUMENT_DIRS.values())},))[name]


def save_manual_creative(root, text, at=None, *, publish=None):
    """组织用户手写创意；发布由调用方注入的 L3 完成。"""
    context = _context(root)
    value = str(text or '')
    if not value.strip():
        raise ValueError('请先填写自己的创意。')
    if not callable(publish):
        raise TypeError('手动创意文件需要由 L3 注入发布器。')
    day = _file_day(at)
    from script_contract import require_natural_script
    require_natural_script(value)
    name = '/'.join(('创意_' + day, project_document_directory('自然剧本'),
                     project_script_filename(context, at=at, file_type='自然剧本',
                                          content='手动创意')))
    return publish(context.root, ({'name': name, 'data': value.encode('utf-8'),
                           'directories': tuple('创意_' + day + '/' + directory
                                                for directory in PROJECT_DOCUMENT_DIRS.values())},))[name]


def is_project_document_text(text):
    """仅让可归入项目设定、大纲或剧本的模型正文进入项目文件。"""
    value = str(text or '').strip()
    return bool(value and any(mark in value for mark in PROJECT_CONTENT_MARKS))


def _brief_plain_text(text, labels):
    """把明确的 Markdown 字段表/标题转成标签行，不推测正文含义。"""
    names = '|'.join(re.escape(label) for label in labels)
    lines, pending = [], ''
    for line in str(text or '').replace('\r\r\n', '\n').splitlines():
        cells = [cell.strip().strip('*').strip() for cell in line.strip().strip('|').split('|')]
        if len(cells) == 2 and (cells[0] in labels or cells[0] == '设定'):
            line = cells[0] + '：' + cells[1]
        heading = re.fullmatch(r'\s*#{1,6}\s+(' + names + r')\s*[：:]?\s*', line)
        if pending:
            if not line.strip():
                continue
            if heading or re.match(r'\s*(?:[-*#]+\s*)?(?:' + names + r')[ *]*[：:\t]', line):
                lines.append(pending + '：')
            else:
                line = pending + '：' + line.strip()
            pending = ''
        if heading:
            pending = heading.group(1)
        else:
            lines.append(line)
    if pending:
        lines.append(pending + '：')
    value = '\n'.join(lines)
    # 只在已知字段之前还原单元格换行，不把任意正文当字段。
    value = re.sub(r'(?:\\n|<br\s*/?>|[；;\t])\s*(?=(?:' + names + r')[ *]*[：:])', '\n', value, flags=re.I)
    value = re.sub(r'(?m)^[ \t]*(?:设定|备注)[：:][ \t]*(?=(?:' + names + r')[ *]*[：:])', '', value)
    return value


def _brief_value(text, labels):
    """从用户常见的“字段：内容”写法中取值，不猜测未明说的信息。"""
    names = '|'.join(re.escape(label) for label in labels)
    match = re.search(r'(?im)(?:^|\t)[ ]*(?:[-*#]+[ \t]*)?(?:' + names + r')[ *]*[：:\t][ \t]*([^\r\n]*)',
                      _brief_plain_text(text, (*BRIEF_CREATION_FIELDS, *INLINE_REQUIRED_LABELS, *labels)))
    value = match.group(1).strip() if match else ''
    labels = BRIEF_CREATION_FIELDS + ('故事主体', '故事主题', '题材类型', '题材', '类型', '风格', '集数',
        '单集时长', '时长', '篇幅', '主要角色', '角色', '故事人物', '人物设定',
        '故事主线', '故事概述', '剧情', '角色物理特征', '外貌特征', '外貌', '形象', '额外要求', '要求')
    if value and any(value in label or label in value for label in labels):
        return ''
    return value


def _brief_fields(raw):
    """把累计的用户原话提取为契约字段；无标签的整段创意仍是故事梗概。"""
    text = str(raw or '').strip()
    from script_contract import normalize_brief
    genre_words = ('都市', '悬疑', '奇幻', '科幻', '仙侠', '武侠', '校园', '爱情', '喜剧', '恐怖', '冒险', '现实')
    genre = _brief_value(text, ('故事题材', '故事主题', '题材类型', '题材', '类型', '风格'))
    if not genre:
        genre = next((word for word in genre_words if word in text), '')
    episodes = _brief_value(text, ('故事集数', '集数'))
    duration = _brief_value(text, ('单集时间', '单集时长', '时长'))
    length = _brief_value(text, ('篇幅',)) or '；'.join(
        part for part in (('故事集数：' + episodes) if episodes else '',
                          ('单集时间：' + duration) if duration else '') if part)
    if not length:
        found = re.search(r'\d+\s*(?:集|分钟|min|字)', text, re.I)
        length = found.group(0) if found else ''
    characters = _brief_value(text, ('故事角色', '主要角色', '角色', '故事人物', '人物设定'))
    if not characters:
        candidate = re.search(r'(?m)^.*(?:主角|男主|女主).+$', text)
        characters = candidate.group(0).strip() if candidate else ''
    fields = {
        'story_summary': _brief_value(text, ('故事梗概', '故事主体', '故事主线', '故事概述', '剧情')) or (
            '' if re.search(r'(?m)^[ \t]*(?:[-*#]+[ \t]*)?(?:故事梗概|故事主体|故事主线|故事概述|剧情)[ \t]*[：:\t]', text) else text),
        'main_characters': characters,
        'physical_features': _brief_value(text, ('物理特征', '角色物理特征', '外貌特征', '外貌', '形象')),
        'genre': genre,
        'length': length,
        'special_requirements': _brief_value(text, ('特殊要求', '内容补充', '额外要求', '要求')),
    }
    return normalize_brief(fields)


def _append_raw_brief(root, text, *, gateway=None):
    """把多轮补充汇总为一个原始简报，供完整性检查读取。"""
    gateway = _require_gateway(gateway)
    path = brief_raw_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = str(text or '').strip()
    if path.is_file():
        previous = path.read_text(encoding='utf-8')
    else:
        old = legacy_brief_raw_path(root)
        previous = old.read_text(encoding='utf-8') if old.is_file() else ''
    if value and value not in previous:
        gateway['publish_text'](path, previous.rstrip() + ('\n\n' if previous.strip() else '') + value + '\n')
    return path


# 表单字段写在这里而不是桌面层：直接输入、表格填写、后续 HOLLMWOOD 契约
# 都经由同一份 brief_creation.md，不会出现两套记忆或两份“原始简报”。
BRIEF_CREATION_FIELDS = (
    '故事集数', '单集时间', '故事画风', '故事梗概', '故事题材',
    '故事角色', '物理特征', '故事分集', '特殊要求', '内容补充',
)


def format_brief_creation(values):
    """将填写表格稳定地保存为人可读的简报文本。"""
    source = values if isinstance(values, dict) else {}
    labels = list(BRIEF_CREATION_FIELDS)
    labels.extend(label for label in source if label not in labels)
    return '\n'.join(label + '：' + str(source.get(label) or '').strip()
                     for label in labels).rstrip() + '\n'


def strip_inline_required_markers(text):
    """行尾必填提示只用于显示，不进入提取、模型输入或项目文件。"""
    return re.sub(r'[ \t]*（必填）[ \t]*(?=\r?$)', '', str(text or ''), flags=re.MULTILINE)


def inline_template_labels(text):
    """从示例的顶层行取得字段边界，缩进角色描述不另起字段。"""
    return tuple(dict.fromkeys(re.findall(r'^([^\s：:][^：:\n]{0,29})[：:]',
                                         str(text or ''), re.MULTILINE)))


def inline_required_missing(template_text, draft_text, required_labels=INLINE_REQUIRED_LABELS,
                            attachment_fields=None, *, stage='script',
                            lock_definitions=PRODUCTION_LOCK_DEFINITIONS):
    """故事字段与本阶段制作锁共用门禁；其他锁只保留为建议值。"""
    lock_definitions = stage_lock_definitions(stage, lock_definitions)
    lock_aliases = {item['label']: (item['label'], *item.get('aliases', ()), item['key'])
                    for item in lock_definitions}
    required_keys = stage_lock_requirements(stage)
    required_labels = tuple(dict.fromkeys((*required_labels,
        *(item['label'] for item in lock_definitions if item['key'] in required_keys))))
    labels = tuple(dict.fromkeys((*inline_template_labels(template_text), *required_labels,
                                 *(label for aliases in lock_aliases.values() for label in aliases))))
    template = extract_brief_creation(strip_inline_required_markers(template_text),
                                      extra_labels=labels, include_extra=True)
    draft = extract_brief_creation(strip_inline_required_markers(draft_text),
                                   extra_labels=labels, include_extra=True)
    def normalized(fields, label):
        return next((''.join(str(fields.get(alias) or '').split())
                     for alias in lock_aliases.get(label, (label,))
                     if str(fields.get(alias) or '').strip()), '')
    return tuple(label for label in required_labels
                 if not normalized(attachment_fields or {}, label)
                 and (not normalized(draft, label)
                      or normalized(draft, label) == normalized(template, label)))


def extract_brief_creation(text, *, extra_labels=(), include_extra=False):
    """只提取明确标注的字段，保留空值和多行；附件不会被当成指令执行。"""
    aliases = {'集数': '故事集数', '单集时长': '单集时间', '时长': '单集时间',
               '主要角色': '故事角色', '角色': '故事角色', '人物设定': '故事角色',
               '题材类型': '故事题材', '题材': '故事题材', '画风': '故事画风',
               '外貌特征': '物理特征', '故事概述': '故事梗概',
               '故事主线': '故事梗概', '故事主体': '故事梗概', '剧情': '故事梗概',
               '故事主题': '故事题材', '类型': '故事题材', '风格': '故事题材',
               '故事人物': '故事角色', '角色物理特征': '物理特征',
               '外貌': '物理特征', '形象': '物理特征', '额外要求': '特殊要求', '要求': '特殊要求'}
    # XLSX 转换稿保留列间制表符；字段可能在“设定”等说明列之后。
    lock_labels = tuple(label for item in PRODUCTION_LOCK_DEFINITIONS
                        for label in (item['label'], *item.get('aliases', ()), item['key']))
    labels = tuple(dict.fromkeys((*BRIEF_CREATION_FIELDS, '篇幅', *aliases, *extra_labels, *lock_labels)))
    label_pattern = '|'.join(re.escape(label) for label in labels)
    fields, active = {}, None
    for line in _brief_plain_text(text, labels).splitlines():
        match = re.search(r'(?:^|\t)[ ]*(?:[-*#]+[ \t]*)?(' + label_pattern
                          + r')[ *]*[：:\t][ \t]*(.*)$', line)
        if match:
            label = match.group(1).strip().strip('*').strip()
            canonical = aliases.get(label, label)
            if canonical in (*BRIEF_CREATION_FIELDS, '篇幅') or (include_extra and label in (*extra_labels, *lock_labels)):
                active = canonical
                fields[active] = match.group(2)
                nested = re.match(r'[ *]*(?:' + label_pattern + r')[ *]*[：:]', match.group(2))
                if nested:
                    fields.update(extract_brief_creation(match.group(2), extra_labels=extra_labels, include_extra=include_extra))
                    active = None
                continue
            if label in labels:
                active = None
                continue
        if active:
            fields[active] += '\n' + line
    length = fields.pop('篇幅', '')
    # 旧简报的篇幅可同时声明集数和单集时长；没有明确时长时不猜默认值。
    for label, pattern in (('故事集数', r'\d+\s*集'),
                           ('单集时间', r'(?:每集|单集)[：:\s]*(\d+(?:\.\d+)?\s*(?:分钟|秒|minutes?|min|s))')):
        match = re.search(pattern, length, re.I)
        if match:
            fields.setdefault(label, match.group(match.lastindex or 0))
    return {label: value.strip() for label, value in fields.items()}


def merge_brief_creation(text, values):
    """只补空字段，保留手填正文、别名、未知字段和原有布局。"""
    source = str(text or '')
    current = extract_brief_creation(source, extra_labels=tuple(values), include_extra=True)
    for label, raw in values.items():
        value = str(raw or '').strip()
        if not value or current.get(label):continue
        replaced = False
        for match in re.finditer(r'(?m)^([^\r\n：:]+)[：:][ \t]*(?=\r?$)', source):
            field = extract_brief_creation(match.group(1) + '：value', extra_labels=tuple(values), include_extra=True)
            if label in field:
                source = source[:match.end()] + value + source[match.end():]
                replaced = True
                break
        if not replaced:
            source += ('\n' if source and not source.endswith('\n') else '') + label + '：' + value
        current[label] = value
    return source


def brief_creation_values(root, extra_text='', *, attachment_values=None, extra_labels=(), attachment_reference=None):
    """读取上次填写内容；当前未发送文本可覆盖同名字段。"""
    path = brief_raw_path(root)
    if path.is_file():
        source = path.read_text(encoding='utf-8')
    else:
        legacy = legacy_brief_raw_path(root)
        source = legacy.read_text(encoding='utf-8') if legacy.is_file() else ''
    current = str(extra_text or '').strip()
    extracted = dict(attachment_values or {})
    for text in (attachment_reference or {}).get('brief_texts', ()):
        for label, value in extract_brief_creation(text, extra_labels=extra_labels).items():
            extracted.setdefault(label, value)
    values = {label: str(extracted.get(label, '')) for label in BRIEF_CREATION_FIELDS}
    values.update(extract_brief_creation(source, extra_labels=extra_labels))
    current_fields = extract_brief_creation(current, extra_labels=extra_labels)
    values.update(current_fields)
    if current and not current_fields and not any(values.values()):
        values['故事梗概'] = current
    return values


def save_brief_creation(root, values, *, gateway=None):
    """保存表格内容到唯一简报文件，并返回可直接发送的文本。"""
    text = strip_inline_required_markers(values) if isinstance(values, str) else format_brief_creation(values)
    path = brief_raw_path(root)
    _require_gateway(gateway)['publish_text'](path, text)
    return path, text


def _brief_source_text(root, raw, *, gateway=None):
    """合并项目内用户已发送的对话，供简报完整性检查复用。"""
    sources = [str(raw or '').strip()]
    seen = {source for source in sources if source}
    for row in _all_rows(root, gateway=gateway):
        if str(row.get('role') or '').strip() != 'user':
            continue
        value = str(row.get('text') or '').strip()
        if value and value not in seen:
            sources.append(value)
            seen.add(value)
    return '\n\n'.join(source for source in sources if source)


def brief_followup(fields):
    """一次性询问所有仍缺的必填信息，不重复索要已提供的内容。"""
    from script_contract import BRIEF_LABELS, missing_brief_fields
    missing = missing_brief_fields(fields)
    if not missing:
        return ''
    labels = '、'.join(BRIEF_LABELS[field] for field in missing)
    return '为了开始创作，请一次补充以下信息：' + labels + '。已提供的内容无需重复。'


BRIEF_ATTACHMENT_NOTICE = '引用附档无本地可读转换稿,请补充填写或改用 .md/.txt 重新上传'


def receive_brief(root, text, workflow=None, lock_definitions=(), *, gateway=None, attachment_reference=None,
                  inline_text=None, inline_template=None, stage='script'):
    """接收用户创意，落盘原始简报；满足必填项时才生成 brief_complete.json。"""
    lock_definitions = stage_lock_definitions(stage, lock_definitions)
    value = str(text or '').strip()
    if not value:
        raise ValueError('请先输入创意')
    gateway = _require_gateway(gateway)
    if inline_text is None:
        raw_path = _append_raw_brief(root, value, gateway=gateway)
        raw = raw_path.read_text(encoding='utf-8')
    else:
        # 当前模板优先；发送启动成功后由调用方覆盖保存，失败不吞掉上一份简报。
        raw_path = brief_raw_path(root)
        raw = strip_inline_required_markers(inline_text)
    extraction_text = '\n'.join((_brief_source_text(root, raw, gateway=gateway),
                                 *(attachment_reference or {}).get('brief_texts', ())))
    lock_sources = [raw, *(attachment_reference or {}).get('brief_texts', ())]
    if inline_text is not None:
        values = extract_brief_creation(raw, extra_labels=inline_template_labels(raw), include_extra=True)
        missing = inline_required_missing(inline_template, raw, tuple(values), stage=None, lock_definitions=lock_definitions) if inline_template is not None else ()
        current = '\n'.join(label + '：' + ' '.join(value.splitlines()) for label, value in values.items()
                            if value.strip() and label not in missing)
        lock_sources = [current, *(attachment_reference or {}).get('brief_texts', ())]
        extraction_text = '\n'.join(lock_sources)
    fields = _brief_fields(extraction_text)
    workflow = dict(workflow or {})
    selected_locks = {}
    name = str(workflow.get('name') or '').strip()
    # 已同步附档与手动配置优先于历史简报；本轮明确填写仍可覆盖。
    configured = (workflow.get('lock') or {}).get(name, {})
    for item in lock_definitions:
        labels = (item['label'], *item.get('aliases', ()), item['key'])
        selected_locks[item['key']] = (_brief_value(str(text or ''), labels)
            or configured.get(item['key'], '')
            or next((value for source in lock_sources
                     if (value := _brief_value(source, labels))), ''))
    fields['production_locks'] = {key: value for key, value in selected_locks.items() if value}
    from script_contract import brief_document, missing_brief_fields
    missing_locks = tuple(item for item in lock_definitions
                          if item['key'] in stage_lock_requirements(stage)
                          and not selected_locks.get(item['key']))
    missing = missing_brief_fields(fields) + tuple(item['key'] for item in missing_locks)
    followup = brief_followup(fields)
    if missing_locks:
        followup += ('\n' if followup else '') + '请补充本阶段制作锁：' + '、'.join(item['label'] for item in missing_locks) + '。'
    result = {'raw_path': raw_path, 'fields': fields, 'missing': missing,
              'followup': followup, 'complete_path': None,
              'attachment_notice': BRIEF_ATTACHMENT_NOTICE if (attachment_reference or {}).get('brief_unreadable') else ''}
    if missing:
        return result
    document = brief_document(fields)
    # 统筹锁在简报和项目投影中各保留一份：前者供人/模型阅读，后者供页面程序查询。
    name = str(workflow.get('name') or '').strip()
    if name:
        locks = fields['production_locks']
        if locks:
            document['brief']['production_locks'] = locks
            document['recommended_missing'] = [item for item in document['recommended_missing']
                                               if item != 'production_locks']
        namespaces = dict(workflow.get('lock') or {})
        namespaces[name] = locks
        workflow['lock'] = namespaces
    path = brief_complete_path(root)
    gateway['publish_json'](path, document)
    result['complete_path'] = path
    # L2 只形成投影数据；L4 调用方经 stage_config 的原子写入口落盘，避免领域服务反向依赖阶段编排层。
    result['workflow_projection'] = workflow if name else None
    return result


def latest_reply(root):
    """最近一份创意文件（模型的输出落的就是这一份）；一份都没有给 None。"""
    files = creative_documents(root)
    return files[-1] if files else None


def initial_brief_document(root):
    """剧本准备页首次打开时应编辑的创意文件。

    优先采用分类创意目录中最新的一份；老项目仍可从剧本准备根目录的 Markdown
    文件恢复，完全没有历史内容时则返回页面可首次保存的默认路径。
    """
    from project_stages import writing
    context = _context(root)
    writing_dir = writing(context.root)
    versions = creative_documents(root)
    if versions:
        return versions[-1]
    legacy = sorted((path for path in writing_dir.glob('*.md') if path.is_file()),
                    key=lambda path: path.stat().st_mtime)
    return legacy[-1] if legacy else default_brief_document(context)


def default_brief_document(root):
    """没有创意历史时，剧本准备页可首次保存的默认路径。"""
    from project_stages import writing
    return writing(_context(root).root) / '创意与剧本.md'


def creative_documents(root):
    """剧本准备阶段可见的创意文件，兼容旧文件但只把新文件写入分类目录。"""
    from project_stages import writing
    writing = writing(_context(root).root)
    # 新文件名不再依赖“创意与剧本”字样；目录本身才是下载版本的唯一归属。
    # 同时保留旧命名文件，让升级后仍能打开历史剧本。
    categories = set(PROJECT_DOCUMENT_DIRS.values())
    batches = []
    try:
        first_level = tuple(writing.iterdir())
    except OSError:
        first_level = ()
    # 当前布局固定为 writing/[Provider]/[Model]/创意_日期；同时兼容没有
    # Provider 或 Model 的历史项目。只枚举这一受控层级，首屏不能 rglob 整个项目。
    for first in first_level:
        try:
            if not first.is_dir() or first.name == '输入':
                continue
        except OSError:
            continue
        if first.name.startswith('创意_'):
            batches.append(first)
            continue
        try:
            second_level = tuple(first.iterdir())
        except OSError:
            continue
        for second in second_level:
            try:
                if not second.is_dir():
                    continue
            except OSError:
                continue
            if second.name.startswith('创意_'):
                batches.append(second)
                continue
            try:
                third_level = tuple(second.iterdir())
            except OSError:
                continue
            batches.extend(path for path in third_level
                           if path.is_dir() and path.name.startswith('创意_'))

    files = []
    for batch in batches:
        try:
            entries = tuple(batch.iterdir())
        except OSError:
            continue
        for path in entries:
            try:
                if path.is_file() and path.suffix.lower() == '.md':
                    # 升级前直系文件只用于读取历史，不参与新的保存和页面分类。
                    files.append(path)
                elif path.is_dir() and path.name in categories:
                    files.extend(item for item in path.iterdir()
                                 if item.is_file() and item.suffix.lower() == '.md')
            except OSError:
                continue
    return tuple(sorted(files,
                        key=lambda path: path.stat().st_mtime if path.exists() else 0))


def history_text(rows, limit=6):
    """最近几轮对话拼成一段（给模型看的上下文；只留最近几轮，前缀别越滚越长）。"""
    lines = []
    for row in list(rows or [])[-limit:]:
        who = '用户' if str(row.get('role')) == 'user' else '模型'
        lines.append(who + '：' + str(row.get('text') or '').strip())
    return '\n'.join(lines)


def history_context(rows, recent_limit=6, char_limit=12000, summary_limit=1800):
    """给模型的有界会话上下文：保留近况，并摘录较早的关键信息。

    聊天原文始终完整保存在本地；这里的“摘要”不调用模型、不落盘，只从较早
    消息的开头抽取有限片段，避免每次请求把长会话全文重新带上。
    """
    clean = [row for row in list(rows or [])
             if isinstance(row, dict) and str(row.get('text') or '').strip()]
    recent_limit = max(1, int(recent_limit))
    char_limit = max(1, int(char_limit))
    compacted = [row for row in clean if row.get('context_compacted') is True]
    if compacted:
        summary = _history_excerpt(compacted, min(summary_limit, char_limit // 3))
        pending = [row for row in clean if row.get('context_compacted') is not True]
        remaining = char_limit - len(summary) - 2
        if not pending or remaining <= 0:
            return summary[:char_limit]
        return summary + '\n\n' + history_context(pending, recent_limit, remaining, summary_limit)
    recent_rows = clean[-recent_limit:]
    early_rows = clean[:-recent_limit]
    recent = history_text(recent_rows, limit=recent_limit)
    if not early_rows:
        return recent[-char_limit:]

    summary = _history_excerpt(early_rows, min(summary_limit, char_limit // 3))
    remaining = max(0, char_limit - len(summary) - 2)
    if not remaining:
        return summary[:char_limit]
    return summary + '\n\n' + recent[-remaining:]


def _history_excerpt(rows, char_limit):
    excerpts = []
    # 早期设定和最近一次已确认内容通常都具有延续价值；中段细节由完整本地历史保留。
    sample = rows[:2] + rows[-4:]
    for row in sample:
        who = '用户' if str(row.get('role')) == 'user' else '模型'
        text = ' '.join(str(row.get('text') or '').split())
        if len(text) > 260:
            text = text[:257] + '…'
        item = who + '：' + text
        if item not in excerpts:
            excerpts.append(item)
    summary = '较早对话摘录（完整记录保存在本地）：\n' + '\n'.join(excerpts)
    return summary[:max(0, char_limit)]


def latest_text(root, model=None, *, gateway=None):
    """最近一条模型的回复正文（定稿时保存的就是它）；没有就是空串。"""
    for row in reversed(load(root, model=model, gateway=gateway)):
        if str(row.get('role')) != 'user':
            return str(row.get('text') or '').strip()
    return ''


def why_empty(result):
    """第 65 期任务 10：模型回了、正文却一个字都没有时，给一句能照做的话。

    用户报过「返回模型没有会话:空回复」——推理型的模型把 max_tokens 全花在思考上时，
    content 就是空的（finish_reason=length）。这跟「网络没通」是两回事，说清楚。
    """
    reason = ''
    data = (result or {}).get('data')
    if isinstance(data, dict):
        choices = data.get('choices')
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            reason = str(choices[0].get('finish_reason') or '')
    if reason == 'length':
        return '模型把这一次的输出额度用完了，正文一个字都没剩下；请把想问的写短一点再发一次。'
    return '模型未返回可显示正文：' + str((result or {}).get('error') or '空回复')


def prompt_for(text, rows=None):
    """提交给模型的整段：先前的对话 ＋ 这一次提交的创意 ＋ 一句要求。"""
    parts = []
    history = history_text(rows)
    if history:
        parts.append('（先前对话）\n' + history)
    parts.append('（本次提交的创意）\n' + str(text or '').strip())
    parts.append('请据此把这份创意写成能直接开拍的漫剧纲要，并指出还缺什么。')
    return '\n\n'.join(parts)


def reply_text(result):
    """从一次调用的返回里取出模型写的字（chat 与 responses 两种回法都认）。"""
    visible_text = str((result or {}).get('text') or '').strip()
    if visible_text:
        return visible_text
    data = (result or {}).get('data')
    if isinstance(data, dict) and isinstance(data.get('content'), (list, tuple)):
        # Messages 的 thinking／signature 从不属于聊天正文。
        from token_saver import anthropic_text
        return anthropic_text(data)
    value = ''
    try:
        from pet_agent import extract_content
        value = extract_content(data)
    except Exception:
        value = ''
    if not value and isinstance(data, dict):
        choices = data.get('choices')
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = first.get('message') if isinstance(first.get('message'), dict) else {}
            value = message.get('content') or first.get('text') or ''
        value = value or data.get('output_text') or ''
    return str(value or '').strip()
