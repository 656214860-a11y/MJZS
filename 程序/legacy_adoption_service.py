# -*- coding: utf-8 -*-
"""旧目录归位日志的受控发布服务。"""
from datetime import datetime
from pathlib import Path
import logging

from contract.stage_layout import ARCHIVE
from contract.service_contract import SystemError, success

LOGGER = logging.getLogger(__name__)


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
    target = folder / '旧目录归位.json'
    timestamp = now or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    payload = {'at': timestamp, 'linked': [str(path) for path in linked_paths]}
    try:
        make_dir(folder)
        publish(target, payload)
    except OSError:
        LOGGER.exception('旧目录归位日志保存失败')
        return SystemError('旧目录归位日志保存失败，请检查文件权限和磁盘空间。')
    return success(target)
