# -*- coding: utf-8 -*-
"""资产文字与图片的版本记录数据层（09 册 §6 / DOC-D9-4，用户 2026-11-21 决定）。

每个资产写入口成功写入后追加一条 JSON Lines 记录：版本号（按资产自增）、
时间、改了什么（``field``/``kind``＋``before``/``after`` 摘要）、来源
（``generated``/``imported``/``manual``）。记录落在
``<资产库>/assets/资产版本/<aid>.jsonl``，经注入或默认发布器原子写整文件；
任何失败只降级写诊断，绝不使资产写入失败。旧资产没有记录文件时读取为空，
不迁移、不补造历史；读取侧容忍缺 ``schema_version`` 的旧行。

``before``/``after`` 摘要口径：文字字段记全量值（改动的键 → 前后值）；
图片记 ``{'path': 资产库内相对路径, 'sha256': 内容哈希}``（``image_summary``）。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from contract.artifact_schema import SCHEMA_VERSION, VERSION_KEY

AID_PATTERN = re.compile(r'(CHAR|LOC|PROP)_\d{3,}')
SOURCES = ('generated', 'imported', 'manual')
_LOG = logging.getLogger('asset_versions')
_LOCKS = {}
_LOCKS_GUARD = threading.Lock()
_DECODER = json.JSONDecoder()


def versions_path(base, aid):
    """版本记录文件路径：``<资产库>/assets/资产版本/<aid>.jsonl``。"""
    aid = str(aid or '').strip()
    if not AID_PATTERN.fullmatch(aid):
        raise ValueError('资产编号不正确：' + (aid or '（空）'))
    # 纯词法归一，不走 resolve()：记录目录在首次写入前不存在，Windows 上对不存在
    # 路径的 realpath 会返回 \\?\ 前缀形态，和已解析的 base 比 is_relative_to 必炸。
    # aid 已被正则锁死（无分隔符/点号），拼进固定两级目录不可能越出资产库。
    root = Path(os.path.normcase(os.path.abspath(os.fspath(base))))
    return root / 'assets' / '资产版本' / (aid + '.jsonl')


def _lock_for(path):
    """按记录文件加进程内锁：版本号＝已有行数＋1，读改写必须串行。"""
    key = str(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = _LOCKS[key] = threading.Lock()
        return lock


def _read_lines(path):
    """读出现有 JSONL 行（去空行）；文件不存在返回空表，其它读故障向上抛。"""
    try:
        raw = Path(path).read_text(encoding='utf-8')
    except FileNotFoundError:
        return []
    return [line for line in raw.splitlines() if line.strip()]


def append_version(base, aid, change, *, source, publish, now=None):
    """成功写入后追加一条版本记录；任何失败返回 ``None``（降级写诊断，不阻断资产写入）。

    ``change`` 为 ``{'field','kind','before','after'}`` 字典：``before``/``after``
    记改动字段的前后摘要（文字全量值；图片用 ``image_summary`` 的路径＋sha256）。
    ``publish(path, text)`` 必须由调用方注入（L2 写入口用各自网关的发布器，
    L4 入口用 ``agent.core.save_text``）；``now`` 仅供测试注入固定时间。
    """
    try:
        if source not in SOURCES:
            raise ValueError('版本记录来源必须是 generated/imported/manual 之一')
        if not callable(publish):
            raise TypeError('版本记录写入需要注入发布器')
        path = versions_path(base, aid)
        aid = str(aid).strip()
        change = change if isinstance(change, dict) else {}
        with _lock_for(path):
            lines = _read_lines(path)
            record = {VERSION_KEY: SCHEMA_VERSION, 'aid': aid,
                      'version': len(lines) + 1,
                      'at': now or datetime.now().isoformat(timespec='seconds'),
                      'field': str(change.get('field') or ''),
                      'kind': str(change.get('kind') or ''),
                      'before': change.get('before'), 'after': change.get('after'),
                      'source': source}
            lines.append(json.dumps(record, ensure_ascii=False))
            publish(path, '\n'.join(lines) + '\n')
        return record
    except Exception as exc:
        _LOG.warning('资产版本记录写入失败（不影响资产写入）：%s', exc)
        return None


def _records(path):
    """解析 JSONL；坏行跳过（读取侧容忍，不向上抛）。

    逐行用 ``JSONDecoder.raw_decode`` 流式解码：JSONL 不是整文档 JSON，
    ``json.loads`` 整行装载既不必要也会被统一棘轮记为未审计直读。
    """
    records = []
    for line in _read_lines(path):
        try:
            record, _end = _DECODER.raw_decode(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def list_versions(project, aid, *, episode_dir=''):
    """只读：某资产的全部版本记录（旧资产无记录返回 ``[]``）。"""
    from domain.asset_context import library_dir
    return _records(versions_path(library_dir(project, episode_dir), aid))


def get_version(project, aid, n, *, episode_dir=''):
    """只读：取第 ``n`` 条版本记录；不存在或编号非法返回 ``None``。"""
    try:
        wanted = int(n)
    except (TypeError, ValueError):
        return None
    for record in list_versions(project, aid, episode_dir=episode_dir):
        if record.get('version') == wanted:
            return record
    return None


def image_summary(path, base):
    """图片版本摘要 ``{'path': 资产库内相对路径, 'sha256': 内容哈希}``；不可用返回 ``None``。

    版本记录绝不阻断资产写入：文件缺失、读不出、越出资产库都返回 ``None``。
    """
    try:
        target = Path(os.path.abspath(os.fspath(path)))
        if not target.is_file():
            return None
        root = Path(os.path.normcase(os.path.abspath(os.fspath(base))))
        prefix = os.path.normcase(str(root)).rstrip(os.sep) + os.sep
        if not os.path.normcase(str(target)).startswith(prefix):
            return None
        return {'path': target.relative_to(root).as_posix(),
                'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    except Exception:
        return None
