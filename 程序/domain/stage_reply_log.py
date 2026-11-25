# -*- coding: utf-8 -*-
"""第 2–13 页「过程与回话区」的分阶段记录层（08 册 §8 / DOC-D8-1，UX-REPLY-AREA）。

每条过程事件追加一行 JSON Lines 到 ``<项目>/对话记录/<阶段键>.jsonl``。写入沿用
``domain.asset_versions`` 口径：进程内按文件加锁、读全行→附加→经注入发布器
（L4 入口用 ``agent.core.save_text``）原子写回；任何失败只降级写诊断，绝不使
发送/回显失败。打开页只经 ``read_tail`` 反向定位读最近 ``limit`` 条（不一次全量
读入），更早记录按字节游标 ``read_before`` 分页；无总条数上限，不在启动路径扫盘。
读取侧容忍缺 ``schema_version`` 的行与坏行。记录仅供回显，严禁进入任何发给
模型的 prompt/上下文。
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

from contract.artifact_schema import SCHEMA_VERSION, VERSION_KEY
from contract import pet_bus

FOLDER = '对话记录'
TAIL_LIMIT = 200
# 反向定位的读取步长（64 KiB）与单次窗口上限（4 MiB，防病态单行耗尽内存）。
_BLOCK = 65536
_WINDOW_CAP = _BLOCK * 64
_KINDS = frozenset({
    'user',       # 用户指令
    'reply',      # 模型/应用回话
    'progress',   # 状态与进度回显
    'approval',   # 审批（schema 预留，生产写入方未接线）
    'artifact',   # 产物行（可点开）
    'error',      # 错误回显
    'tool',       # 工具步骤
    'notice',     # 其他提示
})
_LOG = logging.getLogger('stage_reply_log')
_LOCKS = {}
_LOCKS_GUARD = threading.Lock()
_DECODER = json.JSONDecoder()


def stage_log_path(root, stage_key):
    """分阶段记录文件路径：``<项目>/对话记录/<阶段键>.jsonl``。"""
    stage_key = str(stage_key or '').strip()
    if stage_key not in pet_bus.STAGES:
        raise ValueError('不是有效的制作阶段键：' + (stage_key or '（空）'))
    # 阶段键白名单锁死（无分隔符/点号），拼进固定目录不可能越出项目根。
    base = Path(os.path.normcase(os.path.abspath(os.fspath(root))))
    return base / FOLDER / (stage_key + '.jsonl')


def _lock_for(path):
    key = str(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = _LOCKS[key] = threading.Lock()
        return lock


def _read_lines(path):
    try:
        # errors='replace'：坏字节行降级为替换符占位（读取侧本就跳过），
        # 不让一行坏数据使整文件追加写永远失败。
        raw = Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    return [line for line in raw.splitlines() if line.strip()]


def append_record(root, stage_key, record, *, publish=None, now=None):
    """追加一条过程记录；任何失败返回 ``None``（降级写诊断，不阻断回显链）。

    ``record`` 至少含 ``kind``＋``text``，其余键原样保留（``path``/``parts``/``title``
    等）。``publish(path, text)`` 必须由调用方注入（L4 用 ``agent.core.save_text``）。
    """
    try:
        if not isinstance(record, dict):
            raise TypeError('过程记录必须是字典')
        kind = str(record.get('kind') or '')
        if kind not in _KINDS:
            raise ValueError('未登记的过程记录种类：' + (kind or '（空）'))
        if not callable(publish):
            raise TypeError('过程记录写入需要注入发布器')
        path = stage_log_path(root, stage_key)
        stored = dict(record)
        stored[VERSION_KEY] = SCHEMA_VERSION
        stored['kind'] = kind
        stored.setdefault('at', now or datetime.now().isoformat(timespec='seconds'))
        with _lock_for(path):
            lines = _read_lines(path)
            lines.append(json.dumps(stored, ensure_ascii=False))
            publish(path, '\n'.join(lines) + '\n')
        return stored
    except Exception as exc:
        _LOG.warning('过程回话记录写入失败（不影响回显）：%s', exc)
        return None


def _decode(lines):
    """逐行 ``raw_decode`` 解析 JSONL；坏行与非字典行跳过（读取侧容忍）。"""
    records = []
    for raw in lines:
        try:
            item, _end = _DECODER.raw_decode(
                raw.decode('utf-8') if isinstance(raw, bytes) else raw)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _window(path, end, limit):
    """在 ``(0, end)`` 区间反向定位最后 ``limit`` 个完整行：``(行表, 首行字节偏移)``。

    游标语义：返回值是本次首行起始偏移，0＝已顶到文件头（没有更早记录）。
    ``end=None`` 表示读到文件尾。
    """
    with open(path, 'rb') as handle:
        handle.seek(0, 2)
        size = handle.tell()
        if end is None or end > size:
            end = size
        if end <= 0:
            return [], 0
        pos, buf = end, b''
        while pos > 0:
            step = min(_BLOCK, pos)
            pos -= step
            handle.seek(pos)
            buf = handle.read(step) + buf
            if buf.count(b'\n') > limit or len(buf) > _WINDOW_CAP:
                break
        segments = buf.split(b'\n')
        # 窗口末端截在行中（end 不是行首）：末段半行弃用。end 恰是行首时
        # buf 末字节是 '\n'，split 的末段为 ''，本就过滤，无需特判。
        if end < size and not buf.endswith(b'\n'):
            segments = segments[:-1]
        base = pos
        if pos > 0:
            # 窗口始端截在行中才丢首段；恰好落在行首（pos-1 是 '\n'）则首段完整。
            handle.seek(pos - 1)
            if handle.read(1) != b'\n':
                base = pos + len(segments[0]) + 1
                segments = segments[1:]
        rows = []
        cursor_pos = base
        for line in segments:
            if line.strip():
                rows.append((cursor_pos, line))
            cursor_pos += len(line) + 1
        take = rows[-limit:]
        if pos == 0 and len(take) == len(rows):
            start = 0
        elif take:
            start = take[0][0]
        else:
            # 窗口内没有完整行（单行超窗口上限等病态输入）：游标归零终止分页，
            # 不再回指自身区间造成调用方原地踏步。
            start = 0
        return [line for _offset, line in take], start


def read_tail(root, stage_key, limit=TAIL_LIMIT):
    """打开页只读最近 ``limit`` 条（时间正序）＋更早分页游标；不全量读入。

    返回 ``(records, cursor)``；``cursor == 0`` 表示没有更早记录。
    """
    path = stage_log_path(root, stage_key)
    try:
        lines, cursor = _window(path, None, limit)
    except OSError:
        return [], 0
    return _decode(lines), cursor


def read_before(root, stage_key, cursor, limit=TAIL_LIMIT):
    """按 ``read_tail``/``read_before`` 返回的字节游标加载更早一页。"""
    try:
        end = int(cursor)
    except (TypeError, ValueError):
        return [], 0
    if end <= 0:
        return [], 0
    path = stage_log_path(root, stage_key)
    try:
        lines, cursor = _window(path, end, limit)
    except OSError:
        return [], 0
    return _decode(lines), cursor
