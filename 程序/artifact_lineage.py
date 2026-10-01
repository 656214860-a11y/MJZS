# -*- coding: utf-8 -*-
"""用户可见成果的来源关系账本。"""
from datetime import datetime
from pathlib import Path

from agent.core import file_hash, read_json, save


FILE_NAME = '产物来源关系.json'


def _relative(root, path):
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def _path(artifact):
    return Path(artifact).parent / FILE_NAME


def record(root, artifact, source, artifact_type):
    """原子记录 ``artifact ← source``；同一成果覆盖旧记录。"""
    root, artifact, source = Path(root).resolve(), Path(artifact).resolve(), Path(source).resolve()
    path = _path(artifact)
    rows = read_json(path, default={})
    rows = rows if isinstance(rows, dict) else {}
    entries = rows.get('entries') if isinstance(rows.get('entries'), list) else []
    artifact_rel = _relative(root, artifact)
    item = {'artifact': artifact_rel, 'source': _relative(root, source),
            'artifact_type': str(artifact_type), 'source_sha256': file_hash(source),
            'updated_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}
    entries = [entry for entry in entries if not isinstance(entry, dict)
               or entry.get('artifact') != artifact_rel]
    entries.append(item)
    save(path, {'version': 1, 'entries': entries})
    return path


def source_available(root, artifact):
    """有账本时严格验证源文件仍在；无账本返回 None 交给历史兼容层。"""
    root = Path(root).resolve()
    artifact_rel = _relative(root, artifact)
    rows = read_json(_path(artifact), default={})
    entries = rows.get('entries') if isinstance(rows, dict) else None
    if not isinstance(entries, list):
        return None
    entry = next((row for row in entries if isinstance(row, dict)
                  and row.get('artifact') == artifact_rel), None)
    if entry is None:
        return None
    source = root / str(entry.get('source') or '')
    try:
        return source.is_file() and source.stat().st_size > 0
    except OSError:
        return False
