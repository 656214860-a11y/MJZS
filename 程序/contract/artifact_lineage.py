# -*- coding: utf-8 -*-
"""用户可见成果的来源关系账本。

账本为每个成果记录它依赖的输入（自然剧本、结构剧本、分镜、资产、台词、
模型配置等）以及登记当时的内容摘要，把两件事分开：

- ``available``：来源是否仍在（存在且非空）。缺失时下游可隐藏孤立成果。
- ``status``：来源是否仍是当初登记的这一版（``current``/``stale``/
  ``missing``/``unknown``）。内容变了只标过期，绝不自动删除或覆盖用户成品。
"""
from datetime import datetime
from pathlib import Path

from agent.core import file_hash, read_json, save
import contract.artifact_schema as artifact_schema


FILE_NAME = '产物来源关系.json'
# 成果与来源的关系状态。unknown 表示没有账本或没有该成果记录（历史兼容，
# 交由上层显式采用），不得据此删除任何文件。
CURRENT, STALE, MISSING, UNKNOWN = 'current', 'stale', 'missing', 'unknown'
PRIMARY_ROLE = 'source'


def _relative(root, path):
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def _path(artifact):
    return Path(artifact).parent / FILE_NAME


def _digest(path):
    """内容摘要；读不动（含不存在）时返回空串，交由调用方按 missing 处理。"""
    try:
        return file_hash(path)
    except OSError:
        return ''


def _source_pairs(source, sources):
    """把单来源或多来源调用统一成 [(角色, 路径), ...]，顺序稳定。"""
    if sources:
        pairs = sources.items() if isinstance(sources, dict) else sources
        return [(str(role), path) for role, path in pairs if path is not None]
    return [(PRIMARY_ROLE, source)] if source is not None else []


def record(root, artifact, source=None, artifact_type='', *, sources=None):
    """原子记录 ``artifact ← 一个或多个来源``；同一成果覆盖旧记录。

    ``source`` 保留旧的单来源调用；``sources`` 用于分镜／资产／台词／模型
    配置等多输入成果，接受 ``{角色: 路径}`` 或 ``[(角色, 路径), ...]``。
    每个来源都留下登记当时的内容摘要，使 ``source_status`` 能区分「源仍在」
    与「源仍是这一版」。历史成果不会被自动补账，须显式 :func:`adopt`。
    """
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    pairs = _source_pairs(source, sources)
    if not pairs:
        raise ValueError('来源账本至少需要一个来源。')
    raw = read_json(_path(artifact), default={})
    # D4-c/D4-d：属主读取点分类计数；future 账本拒写——保留新格式文件不覆盖，
    # 本次登记跳过（该成果退回「无账本」兼容口径，不影响阶段完成）。
    # L0 不能 import 播报层，【警告】由诊断计数承接（见结果文件欠账说明）。
    state = artifact_schema.classify('artifact_lineage', raw)
    artifact_schema.note_read_state('artifact_lineage', state)
    if state == 'future':
        return _path(artifact)
    rows = raw if isinstance(raw, dict) else {}
    entries = rows.get('entries') if isinstance(rows.get('entries'), list) else []
    artifact_rel = _relative(root, artifact)
    recorded = []
    for role, path in pairs:
        path = Path(path)
        path = path if path.is_absolute() else Path(root) / path
        recorded.append({'role': role, 'path': _relative(root, path),
                         'sha256': _digest(path)})
    primary = recorded[0]
    item = {'artifact': artifact_rel, 'artifact_type': str(artifact_type),
            'source': primary['path'], 'source_sha256': primary['sha256'],
            'sources': recorded,
            'updated_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}
    entries = [entry for entry in entries if not isinstance(entry, dict)
               or entry.get('artifact') != artifact_rel]
    entries.append(item)
    # D4-e/G8：正常写入双写 schema_version 与旧键 version，旧版程序仍能读。
    save(_path(artifact), artifact_schema.stamp('artifact_lineage', {'version': 1, 'entries': entries}))
    return _path(artifact)


def adopt(root, artifact, source=None, artifact_type='', *, sources=None):
    """无账本旧项目显式采用：把现有成果与当前来源登记为一致，不自动补账。"""
    return record(root, artifact, source, artifact_type, sources=sources)


def _entry_sources(entry):
    """兼容旧账本只写 ``source``/``source_sha256`` 的单来源形态。"""
    items = entry.get('sources')
    if isinstance(items, list) and items:
        return [item for item in items if isinstance(item, dict)]
    return [{'role': PRIMARY_ROLE, 'path': entry.get('source') or '',
             'sha256': entry.get('source_sha256') or ''}]


def _overall(rows):
    statuses = {row['status'] for row in rows}
    if MISSING in statuses:
        return MISSING
    if STALE in statuses:
        return STALE
    if CURRENT in statuses:
        return CURRENT
    return UNKNOWN


def _report(root, entry):
    rows = []
    for item in _entry_sources(entry):
        relative = str(item.get('path') or '')
        path = root / relative
        try:
            present = path.is_file() and path.stat().st_size > 0
        except OSError:
            present = False
        recorded = str(item.get('sha256') or '')
        if not present:
            status = MISSING
        elif not recorded:
            status = UNKNOWN
        else:
            status = CURRENT if _digest(path) == recorded else STALE
        rows.append({'role': str(item.get('role') or PRIMARY_ROLE),
                     'path': relative, 'status': status,
                     'recorded_sha256': recorded})
    return {'artifact': str(entry.get('artifact') or ''),
            'artifact_type': str(entry.get('artifact_type') or ''),
            'status': _overall(rows), 'sources': rows}


def _entry(root, artifact):
    rows = read_json(_path(artifact), default={})
    state = artifact_schema.classify('artifact_lineage', rows)
    artifact_schema.note_read_state('artifact_lineage', state)
    entries = rows.get('entries') if isinstance(rows, dict) else None
    if not isinstance(entries, list):
        return None
    artifact_rel = _relative(root, artifact)
    return next((row for row in entries if isinstance(row, dict)
                 and row.get('artifact') == artifact_rel), None)


def check(root, artifact):
    """逐来源比对登记摘要，返回该成果的版本状态与逐来源明细。

    ``status`` 取 current／stale／missing／unknown；``unknown`` 表示没有账本
    或没有该成果记录（历史项目）。调用方可据此展示「已过期」，但不得据此
    删除或覆盖用户成品。
    """
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    entry = _entry(root, artifact)
    if entry is None:
        return {'artifact': _relative(root, artifact), 'artifact_type': '',
                'status': UNKNOWN, 'sources': []}
    return _report(root, entry)


def source_status(root, artifact):
    """只取整体状态：current／stale／missing／unknown。"""
    return check(root, artifact)['status']


def source_available(root, artifact):
    """有账本时严格验证源文件仍在；无账本返回 None 交给历史兼容层。"""
    rows = check(root, artifact)['sources']
    if not rows:
        return None
    return all(row['status'] != MISSING for row in rows)


def affected(root, source=None):
    """列出已过期（stale）或来源缺失（missing）的成果；给定 source 时只看依赖它的。

    只读遍历项目内的账本文件，供「修改上游后提示受影响成果」使用；不删除、
    不覆盖、不修复任何成品，也不为无账本的历史文件补账。
    """
    root = Path(root).resolve()
    target = None if source is None else _relative(root, source)
    found = []
    for ledger in sorted(root.rglob(FILE_NAME)):
        rows = read_json(ledger, default={})
        state = artifact_schema.classify('artifact_lineage', rows)
        artifact_schema.note_read_state('artifact_lineage', state)
        entries = rows.get('entries') if isinstance(rows, dict) else None
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            report = _report(root, entry)
            if report['status'] in (CURRENT, UNKNOWN):
                continue
            if target is not None and not any(row['path'] == target
                                              for row in report['sources']):
                continue
            found.append(report)
    return found
