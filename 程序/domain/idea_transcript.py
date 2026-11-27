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
import threading
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import infra.business_log as business_log
from domain import message_parts
from contract.project_context import ProjectContext
from domain.idea_document_paths import ChatModel


FOLDER = '创意对话'
CHAT_NAME = '对话.json'
_HISTORY_CACHE_LIMIT = 16
_history_cache = OrderedDict()
# ``_history_cache`` 的 get→move_to_end、set→move_to_end→popitem(last=False)、
# pop 与全部清空路径必须在这把锁内原子完成，否则并发命中/写入/淘汰交错会抛
# KeyError；淘汰上限判断也在锁内。JSON 读写等 IO 一律放在锁外。
_HISTORY_CACHE_LOCK = threading.RLock()


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
    from contract.project_stages import writing
    return writing(_context(context).root) / FOLDER


def history_path(root):
    """旧版统一聊天记录位置；只作为一次性兼容导入源。"""
    return folder(root) / CHAT_NAME


def chat_model(model):
    if isinstance(model, ChatModel):
        return model
    import infra.model_pool as model_pool
    shown = str(model or '').strip()
    records = model_pool.pool(program=Path(__file__).resolve().parents[1])
    matches = [key for key, record in records.items() if record.get('label') == shown]
    key = shown if shown in records else (matches[0] if len(matches) == 1 else '')
    if len(matches) > 1 and not key:
        raise ValueError('模型显示名重复，请通过模型 ID 选择会话')
    record = records.get(key, {})
    return ChatModel(str(record.get('label') or shown), key,
                     model_pool.provider_name(key, record) if key else '')


def model_history_path(context, model, provider=''):
    """单一创意对话目录（任务书轮 4）：所有模型共用 ``创意对话/对话.json``，
    不再按 ``模型会话/<模型>/创意对话/`` 分目录；``model``／``provider`` 仅作行内署名。"""
    return history_path(context)


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
        with _HISTORY_CACHE_LOCK:
            _history_cache.pop(path, None)
        return []
    fingerprint = (stat.st_mtime_ns, stat.st_size)
    with _HISTORY_CACHE_LOCK:
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
    rows = [message_parts.ensure_parts(dict(row)) for row in rows if isinstance(row, dict)]
    rows = [row for row in rows if message_parts.has_content(row)]
    with _HISTORY_CACHE_LOCK:
        _history_cache[path] = (fingerprint, tuple(rows))
        _history_cache.move_to_end(path)
        while len(_history_cache) > _HISTORY_CACHE_LIMIT:
            _history_cache.popitem(last=False)
    return [dict(row) for row in rows]


def _merge_legacy_model_files(root, gateway):
    """旧 ``<写作区>/<提供方>/<模型>/创意对话/对话.json`` 首次读取时并入单一创意对话文件。

    只迁移不删旧文件（任务书轮 4）：旧目录原样保留，统一文件按 ``at`` 时间归并、
    按整行指纹去重；已并入的旧文件下次读取不再重复发布。
    """
    from contract.project_stages import writing
    base = writing(_context(root).root)
    target = Path(history_path(root))
    current = _read_rows(target, gateway)
    seen = {json.dumps(row, ensure_ascii=False, sort_keys=True) for row in current}
    extra = []
    if base.is_dir():
        for path in base.glob('*/*/' + FOLDER + '/' + CHAT_NAME):
            path = Path(path)
            if path == target:
                continue
            for row in _read_rows(path, gateway):
                fingerprint = json.dumps(row, ensure_ascii=False, sort_keys=True)
                if fingerprint not in seen:
                    seen.add(fingerprint)
                    extra.append(row)
    if not extra:
        return
    merged = sorted(current + extra, key=lambda row: str(row.get('at') or ''))
    save_rows(root, merged, gateway=gateway)


def _all_rows(root, model=None, provider='', *, gateway=None):
    """读取聊天记录：单一创意对话目录，旧模型目录已并入（只迁移不删旧文件）。

    ``model``／``provider`` 只影响调用方的行级筛选（``_row_indexes``），不再决定文件位置。
    """
    gateway = _require_gateway(gateway)
    _merge_legacy_model_files(root, gateway)
    return _read_rows(history_path(root), gateway)


def load(root, model=None, *, gateway=None):
    """读取对话；指定模型时只返回该模型自己的聊天页。

    ``role='notice'`` 的说明行（REQ-S01-118）不进按模型的加载结果：模型上下文拼接、
    最近回复定位与按模型导出都走这条路，说明行只给界面看。``model`` 为空的全量
    读取仍包含它，界面按 ``_model_tab_rows`` 把它摆回所属模型的目录条下。
    """
    rows = _all_rows(root, model=model, gateway=gateway)
    key = str(model or '').strip()
    if not key:
        return rows
    selected = [rows[index] for index in _row_indexes(rows, model)
                if str(rows[index].get('role') or '') != 'notice']
    if selected:
        return selected
    # 旧版本的对话没有 model 字段。仅当整个文件都是这种旧格式时才展示它，
    # 防止已分区的新对话在切换模型后串到另一个聊天页。
    if rows and not any(str(row.get('model') or '').strip() for row in rows):
        return rows
    return []


def append(root, role, text, at=None, model=None, *, gateway=None, context_budget=None, request_usage=None, skill_injection=None):
    """记一轮对话（读回来再追加，原子写：写坏一次不会把整段对话丢掉）。"""
    started = time.perf_counter()
    outcome = 'error'
    try:
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
        result = save_rows(root, rows, model=model, gateway=gateway)
        outcome = 'ok'
        return result
    finally:
        # 对话正文属用户内容，绝不进字段；只记阶段、成败与耗时。
        business_log.log_event('idea_transcript.append', stage='script',
                               outcome=outcome,
                               cost_ms=round((time.perf_counter() - started) * 1000.0, 1))


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
            repaired.append(message_parts.set_text(item, text))
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
        # 单一创意对话目录里 ``model`` 为空的行归属不明，不能再按"本文件属于该模型"补写 model_id。
        rows = [dict(row, model_id=identity.model_id)
                if not row.get('model_id') and str(row.get('model') or '') in (str(identity), identity.model_id)
                else dict(row) for row in rows]
    rows = [message_parts.ensure_parts(row) for row in rows]
    path = model_history_path(root, model, provider=provider) if str(model or '').strip() else history_path(root)
    gateway['publish_json'](path, {'version': 1, message_parts.VERSION_KEY: message_parts.SCHEMA_VERSION, 'messages': rows})
    try:
        stat = path.stat()
        clean = tuple(dict(row) for row in rows if isinstance(row, dict) and message_parts.has_content(row))
        with _HISTORY_CACHE_LOCK:
            _history_cache[path] = ((stat.st_mtime_ns, stat.st_size), clean)
            _history_cache.move_to_end(path)
            while len(_history_cache) > _HISTORY_CACHE_LIMIT:
                _history_cache.popitem(last=False)
    except OSError:
        with _HISTORY_CACHE_LOCK:
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
    rows[indexes[index]] = message_parts.set_text(rows[indexes[index]], value)
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
    # 旧版目录改名／迁移会留下同一条消息的其余副本；不一并移除，「全部」视图里它会重新冒出来。
    _drop_rows(root, lambda item: _same_message(item, removed), gateway=gateway,
               skip=(model_history_path(root, model),))
    return saved


def _chat_files(root):
    """项目里所有聊天记录文件：旧版统一文件＋各 Provider／模型目录（含旧版改名残留）。"""
    from contract.project_stages import writing
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
    model = str(row.get('model') or '').strip()
    own = model_history_path(root, model) if model else None
    # 恢复时插回原处：先在该模型会话里找这条的下标，找不到（只在旧版残留里）按时间排位。
    current = _all_rows(root, model=model or None, gateway=gateway)
    index = next((i for i, item in enumerate(current) if isinstance(item, dict) and _same_message(item, row)),
                 sum(1 for item in current if isinstance(item, dict)
                     and str(item.get('at') or '') <= str(row.get('at') or '')))
    removed = _drop_rows(root, lambda item: _same_message(item, row), gateway=gateway,
                         backup=gateway.get('recycle_paths'), unbacked=(own,) if own else ())
    if not removed:
        raise ValueError('这条对话已不存在，请刷新后重试')
    trash = deleted_history_path(root, model=model or None)
    try:
        history = gateway['read_json'](trash) if trash.is_file() else {}
    except (OSError, ValueError):
        history = {}
    records = history.get('messages') if isinstance(history, dict) else []
    records = records if isinstance(records, list) else []
    records.append({'row': dict(row), 'index': index, 'model': model,
                    'model_id': chat_model(model).model_id if model else '', 'deleted_at': _stamp()})
    gateway['publish_json'](trash, {'version': 1, 'messages': records[-100:]})
    return removed


def _message_key(row):
    """跨副本去重键：忽略派生的 ``parts`` 与落盘补写的 ``model_id``。

    ``parts`` 由 ``text``／``thinking`` 派生（R3102），旧版残留文件里的行还没有
    ``parts``；按完整 JSON 比较会把同一条消息误判成两条。身份仍以 role/text/at 等
    原始字段为准。
    """
    if not isinstance(row, dict):
        return json.dumps(row, ensure_ascii=False, sort_keys=True)
    return json.dumps({key: value for key, value in row.items() if key not in ('model_id', 'parts')},
                      ensure_ascii=False, sort_keys=True)


def _same_message(left, right):
    """同一条消息的不同副本：忽略落盘时补写的 ``model_id`` 与派生 ``parts``。"""
    return _message_key(left) == _message_key(right)


def same_message(left, right):
    """界面层按模型标签合并显示时用的同一判据（见 ``_same_message``）。"""
    return isinstance(left, dict) and isinstance(right, dict) and _same_message(left, right)


def _drop_rows(root, matches, *, gateway, skip=(), backup=None, unbacked=()):
    """从项目所有聊天文件里移除 ``matches`` 命中的整条记录，返回移除条数。

    给了 ``backup``（回收入口）时分两步：先把要改写的原文件各备份一份并一次移入回收站，
    全部成功后才改写；任何一份没进回收站就报错且一个文件都不改，不留半删状态。
    ``unbacked`` 里的文件（该模型自己的会话，删除记录已在最近删除里）不做备份。
    """
    skip = {Path(path) for path in skip}
    unbacked = {Path(path) for path in unbacked}
    plans = []
    for path in _chat_files(root):
        if path in skip:
            continue
        try:
            data = gateway['read_json'](path)
        except (OSError, ValueError):
            continue
        rows = data.get('messages') if isinstance(data, dict) else data
        if not isinstance(rows, list):
            continue
        left = [item for item in rows if not (isinstance(item, dict) and matches(item))]
        if len(left) != len(rows):
            plans.append((path, data, rows, left))
    if callable(backup):
        copies = []
        for path, data, _rows, _left in plans:
            if path not in unbacked:
                copy = path.with_name(path.stem + '.删除前备份' + path.suffix)
                gateway['publish_json'](copy, data)
                copies.append(copy)
        if copies:
            backup(_context(root).root, copies, '删除聊天信息')
            if any(copy.exists() for copy in copies):
                raise OSError('聊天记录备份未能移入回收站，请重试')
    removed = 0
    for path, data, rows, left in plans:
        removed += len(rows) - len(left)
        payload = dict(data, messages=left) if isinstance(data, dict) else {'version': 1, 'messages': left}
        gateway['publish_json'](path, payload)
        with _HISTORY_CACHE_LOCK:
            _history_cache.pop(path, None)
    return removed


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
    # 先清旧版改名残留里署名为该模型的记录（不然清空后标签仍在、记录从残留里重新显示）：
    # 备份全部进回收站才改写，失败就整体中止，本模型文件此时还没动。
    label = str(model).strip()
    own_path = model_history_path(root, model)
    identity = chat_model(model)

    def _mine(item):
        """与 ``_row_indexes`` 同口径：优先稳定 model_id，否则按显示名／调用名匹配。"""
        if not isinstance(item, dict):
            return False
        if item.get('model_id') and identity.model_id:
            return item.get('model_id') == identity.model_id
        return str(item.get('model') or '').strip() in (label, str(identity))

    # 单一创意对话目录落地后，旧目录残留下多是已迁移进统一文件的同一批消息：
    # 只有统一文件里没有的残留才算额外删除，否则同一条消息会被数两遍。
    seen = {_message_key(row) for row in rows}
    extra = 0
    for path in _chat_files(root):
        if path == own_path:
            continue
        try:
            data = gateway['read_json'](path)
        except (OSError, ValueError):
            continue
        items = data.get('messages') if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        extra += sum(1 for item in items if _mine(item) and _message_key(item) not in seen)
    _drop_rows(root, _mine, gateway=gateway, skip=(own_path,), backup=recycle)
    legacy = _read_rows(legacy_path, gateway)
    selected = set(_row_indexes(legacy, model))
    remaining = [row for index, row in enumerate(legacy) if index not in selected]
    # 统一文件混放所有模型：只有本模型确有行可删时才整文件回收（回收后按 remaining 重写
    # 其他模型的行）；本模型在统一文件里没有行时不能碰它，否则别家对话会被一起删掉。
    paths = [own_path] if selected else []
    # 最近删除记录同样跨模型混在统一文件里：只摘除本模型的记录，其他模型的保留；
    # 全部记录都属本模型时才连文件一起回收（对齐旧版按模型分文件的口径）。
    trash = deleted_history_path(root, model=model)
    kept_records = None
    try:
        history = gateway['read_json'](trash) if trash.is_file() else {}
    except (OSError, ValueError):
        history = {}
    records = history.get('messages') if isinstance(history, dict) else []
    records = records if isinstance(records, list) else []
    kept = [record for record in records if not (
        isinstance(record, dict) and (
            (record.get('model_id') == identity.model_id)
            if record.get('model_id') and identity.model_id
            else str(record.get('model') or '').strip() in (label, str(identity))))]
    if len(kept) != len(records):
        if kept:
            kept_records = kept
        elif trash.is_file():
            paths.append(trash)
    if paths:
        try:
            recycle(_context(root).root, paths, '删除全部聊天信息')
            if any(path.exists() for path in paths):
                raise OSError('部分聊天记录未能移入回收站，请重试')
        finally:
            if selected and remaining and not legacy_path.exists():
                save_rows(root, remaining, gateway=gateway)
    if kept_records is not None:
        gateway['publish_json'](trash, {'version': 1, 'messages': kept_records})
    return len(rows) + extra


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
               if isinstance(record, dict) and (
                   not key or (
                       (record.get('model_id') == identity.model_id)
                       if record.get('model_id') and identity.model_id
                       else str(record.get('model') or '') == key))
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
