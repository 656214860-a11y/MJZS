# -*- coding: utf-8 -*-
"""旧目录归位日志的受控发布服务。"""
from datetime import datetime
from pathlib import Path

from agent.core import save
from stage_layout import ARCHIVE


def record_legacy_adoption(project, linked_paths, now=None):
    """原子记录本次接入的旧目录，并返回唯一日志路径。"""
    root = Path(project)
    folder = root / ARCHIVE / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / '旧目录归位.json'
    timestamp = now or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save(target, {'at': timestamp, 'linked': [str(path) for path in linked_paths]})
    return target
