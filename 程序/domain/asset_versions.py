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
import uuid
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
            if change.get('restore_of') is not None:
                record['restore_of'] = int(change['restore_of'])
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


_UNSET = object()
_RESTORE_GATEWAY = ('read_json', 'publish_json', 'publish_bytes', 'copy_file')


def _delta(record):
    """一条记录的文字前后值与图片前后摘要；坏行与形状不一的记录容忍。"""
    record = record if isinstance(record, dict) else {}
    before = record.get('before')
    after = record.get('after')
    if record.get('kind') == 'image':
        return {}, {}, before, after
    if record.get('kind') == 'restore':
        # 退回记录的 before/after 是 {'fields':…, 'image':…} 复合形状，拆开参与重建。
        before = before if isinstance(before, dict) else {}
        after = after if isinstance(after, dict) else {}
        return (before.get('fields') if isinstance(before.get('fields'), dict) else {},
                after.get('fields') if isinstance(after.get('fields'), dict) else {},
                before.get('image', _UNSET), after.get('image', _UNSET))
    return (before if isinstance(before, dict) else {},
            after if isinstance(after, dict) else {}, _UNSET, _UNSET)


def describe(record):
    """版本记录的一句话摘要：退回 > 换图片 > 改名 > 改了哪些键。"""
    record = record if isinstance(record, dict) else {}
    if record.get('restore_of') is not None:
        return '退回第 %s 版' % record['restore_of']
    if record.get('kind') == 'image':
        return '换图片'
    before = record.get('before')
    after = record.get('after')
    keys = [str(key) for key in after] if isinstance(after, dict) else []
    if record.get('field') == 'name':
        return '改名：%s → %s' % ((before or {}).get('name'), (after or {}).get('name'))
    if keys:
        return '改了 ' + '、'.join(keys)
    return str(record.get('field') or '内容改动')


def snapshot_at(records, n):
    """重建第 ``n`` 版之后的内容状态：``{'fields': {键: 值}, 'image': 摘要|None}``。

    文字按记录的 ``after`` 全量值逐键累加；``n`` 版之后又被改过的键退回该键
    在第一次改动前的 ``before``；值为 ``None`` 表示那一版没有这一项。
    ``image`` 键只在记录覆盖到图片时才出现。
    """
    wanted = int(n)
    fields = {}
    image = _UNSET
    earlier = {}
    earlier_image = _UNSET
    for record in records or []:
        version = record.get('version') if isinstance(record, dict) else None
        if not isinstance(version, int):
            continue
        before_text, after_text, before_image, after_image = _delta(record)
        if version <= wanted:
            fields.update(after_text)
            if after_image is not _UNSET:
                image = after_image
        else:
            for key, value in before_text.items():
                earlier.setdefault(key, value)
            if earlier_image is _UNSET and before_image is not _UNSET:
                earlier_image = before_image
    for key, value in earlier.items():
        fields.setdefault(key, value)
    out = {'fields': fields}
    if image is not _UNSET:
        out['image'] = image
    elif earlier_image is not _UNSET:
        out['image'] = earlier_image
    return out


def _sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _history_dir(file):
    """图片所在目录的历史版本目录；文件本身就在历史目录里时不再下钻。"""
    parent = Path(file).parent
    return parent if parent.name == '历史版本' else parent / '历史版本'


def _find_version_file(base, aid, target):
    """按记录的 path 与 sha256 找那一版的图片文件：原路径优先，同内容历史备份兜底。"""
    target = target if isinstance(target, dict) else {}
    want = str(target.get('sha256') or '')
    rel = str(target.get('path') or '')
    if not rel:
        return None
    root = Path(base).resolve()
    candidate = (root / rel).resolve()
    if candidate.is_file() and candidate.is_relative_to(root):
        if not want or _sha256(candidate) == want:
            return candidate
    folder = _history_dir(candidate)
    if not want or not folder.is_dir() or not folder.is_relative_to(root):
        return None
    for name in sorted(os.listdir(folder)):
        candidate = folder / name
        if candidate.is_file() and _sha256(candidate) == want:
            return candidate
    return None


def restore_version(base, aid, n, *, gateway=None):
    """退回第 ``n`` 版：把记录过的字段与图片恢复到那一版之后的状态（DOC-D9-4）。

    自身也追加一条 ``source='manual'``、``restore_of=n`` 的新记录，历史一条不删；
    图片退回把那一版的图设为当前图、当前图复制进历史版本后回收。锁定资产、
    记录不存在、旧图找不回都抛 ``ValueError``，且当前内容一字不动。
    ``gateway`` 必须含 read_json／publish_json／publish_bytes／copy_file（L3 注入）。
    """
    if not isinstance(gateway, dict) or any(not callable(gateway.get(k)) for k in _RESTORE_GATEWAY):
        raise TypeError('版本退回需要由 L3 注入读写网关')
    base = Path(base).resolve()
    aid = str(aid or '').strip()
    if not AID_PATTERN.fullmatch(aid):
        raise ValueError('资产编号不正确：' + (aid or '（空）'))
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise ValueError('版本号不正确：' + str(n))
    records = _records(versions_path(base, aid))
    if not any(record.get('version') == n for record in records):
        raise ValueError('没有第 %d 版记录' % n)
    plan_file = base / 'assets/资产清单/assets.json'
    registry_file = base / 'assets.json'
    plan = gateway['read_json'](plan_file) if plan_file.is_file() else {}
    if not isinstance(plan, dict):
        raise ValueError('资产清单 assets.json 顶层必须为对象')
    row = plan.get(aid)
    row = row if isinstance(row, dict) else {}
    if row.get('locked'):
        raise ValueError(aid + ' 已锁定：先解锁再退回历史版本')
    snap = snapshot_at(records, n)
    fields = snap['fields']
    changed = {}
    for key, value in fields.items():
        if value is None:
            if key in row:
                changed[key] = None
        elif row.get(key) != value:
            changed[key] = value
    registry = gateway['read_json'](registry_file) if registry_file.is_file() else {}
    if not isinstance(registry, dict):
        registry = {}
    entry = registry.get(aid)
    entry = entry if isinstance(entry, dict) else {}
    rel = str(entry.get('image') or '')
    current_file = (base / rel).resolve() if rel else None
    if not (current_file and current_file.is_relative_to(base) and current_file.is_file()):
        current_file = None
    current_summary = image_summary(current_file, base) if current_file is not None else None
    target = snap.get('image', _UNSET)
    image_change = target is not _UNSET and not (
        isinstance(target, dict) and current_summary
        and target.get('sha256') == current_summary.get('sha256'))
    source = None
    if image_change and target is not None:
        source = _find_version_file(base, aid, target)
        if source is None:
            raise ValueError('第 %d 版的图已不在资产库（%s），无法退回'
                             % (n, target.get('path') or ''))
    publish = lambda path, text: gateway['publish_bytes'](path, text.encode('utf-8'))
    if not changed and not image_change:
        return append_version(base, aid,
                              {'field': 'restore', 'kind': 'restore',
                               'before': {}, 'after': {}, 'restore_of': n},
                              source='manual', publish=publish)
    from infra import unit_of_work
    backup = None
    if image_change and current_file is not None:
        history = _history_dir(current_file)
        backup = history / (current_file.stem + '_' + uuid.uuid4().hex[:8]
                            + current_file.suffix)
    token = unit_of_work.begin([path for path in
                                (plan_file if changed else None, registry_file, backup)
                                if path is not None])
    try:
        if backup is not None:
            backup.parent.mkdir(parents=True, exist_ok=True)
            gateway['copy_file'](current_file, backup)
        if changed:
            new_row = dict(row)
            for key, value in changed.items():
                if value is None:
                    new_row.pop(key, None)
                else:
                    new_row[key] = value
            updated = dict(plan)
            updated[aid] = new_row
            gateway['publish_json'](plan_file, updated)
        new_entry = dict(entry)
        if image_change:
            if target is None:
                new_entry.pop('image', None)
            else:
                new_entry['image'] = source.relative_to(base).as_posix()
        if 'name' in changed:
            if changed['name'] is None:
                new_entry.pop('name', None)
            else:
                new_entry['name'] = changed['name']
        if new_entry != entry:
            updated_registry = dict(registry)
            updated_registry[aid] = new_entry
            gateway['publish_json'](registry_file, updated_registry)
        unit_of_work.commit(token)
    except BaseException:
        try:
            unit_of_work.rollback(token)
        except Exception:
            _LOG.warning('版本退回回滚失败')
        raise
    if backup is not None:
        try:
            from infra.storage_maintenance import recycle_paths
            recycle_paths(base, (current_file,), '退回第 %d 版替换当前图' % n)
        except Exception:
            _LOG.warning('退回第 %d 版：当前图移回收站失败', n)
    before = {}
    after = {}
    if changed:
        before['fields'] = {key: row.get(key) for key in changed}
        after['fields'] = {key: fields[key] for key in changed}
    if image_change:
        before['image'] = current_summary if backup is None else image_summary(backup, base)
        after['image'] = image_summary(source, base) if target is not None else None
    return append_version(base, aid,
                          {'field': 'restore', 'kind': 'restore',
                           'before': before, 'after': after, 'restore_of': n},
                          source='manual', publish=publish)
