# -*- coding: utf-8 -*-
"""旧目录归位日志的受控发布服务。"""
from datetime import datetime
from pathlib import Path

from stage_layout import ARCHIVE


def _require_gateway(gateway):
    gateway = gateway if isinstance(gateway, dict) else {}
    publish = gateway.get('publish_json')
    make_dir = gateway.get('make_dir')
    if not callable(publish) or not callable(make_dir):
        raise TypeError('旧目录归位记录需要 L3 注入发布网关')
    return publish, make_dir


def record_legacy_adoption(project, linked_paths, now=None, *, gateway=None):
    """原子记录本次接入的旧目录，并返回唯一日志路径。"""
    root = Path(project)
    folder = root / ARCHIVE / 'logs'
    publish, make_dir = _require_gateway(gateway)
    make_dir(folder)
    target = folder / '旧目录归位.json'
    timestamp = now or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    publish(target, {'at': timestamp, 'linked': [str(path) for path in linked_paths]})
    return target
