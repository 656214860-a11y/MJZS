"""视频提示词的可见成果发布；界面只提交镜头编号与文本。"""
from __future__ import annotations

import copy
import json
import logging
from functools import wraps
from pathlib import Path
from contract.service_contract import SystemError, UserError, success

from agent.core import fingerprint, read
from domain.project_naming import dated_path


LOGGER = logging.getLogger('video_prompt_publication')


def _publication_result(operation):
    @wraps(operation)
    def run(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except OSError:
            LOGGER.exception('视频提示词保存失败')
            return SystemError('视频提示词保存失败，请检查文件权限和磁盘空间。')
    return run


def _publish_legacy_bundle(artifacts, *, publish_bundle=None):
    """兼容命名入口；发布实现只能由 L3 注入。"""
    if not callable(publish_bundle):
        raise TypeError('视频提示词发布需要 L3 注入事务发布器')
    return publish_bundle(artifacts, lambda _items: True, lambda: None)


@_publication_result
def publish(studio, sid, text, *, publish_bundle=None):
    """原子发布单镜头提示词及其三个可见副本，再更新分镜索引。"""
    sid = str(sid)
    text = str(text).strip()
    if not text or len(text) > 1500:
        return UserError('提示词须为1–1500个字符')
    episode_path = Path(studio.episode_path)
    episode = read(episode_path)
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        return UserError('镜头不存在：' + sid)
    shot['video_prompt'] = text
    folder = Path(studio.media_dir) / 'video_prompts'
    targets = (
        folder / (sid + '.json'),
        folder / (sid + '.txt'),
        Path(studio.shot_folder(sid)) / '当前提示词.txt',
        episode_path,
    )
    record = {'shot_id': sid, 'source_signature': fingerprint(shot), 'video_prompt': text}
    artifacts = {
        targets[0]: json.dumps(record, ensure_ascii=False, indent=2).encode('utf-8'),
        targets[1]: text.encode('utf-8'),
        targets[2]: text.encode('utf-8'),
        episode_path: json.dumps(episode, ensure_ascii=False, indent=2).encode('utf-8'),
    }
    _publish_legacy_bundle(artifacts, publish_bundle=publish_bundle)
    studio.episode = episode
    return success(copy.deepcopy(record))


def _import_gateway(gateway):
    gateway = gateway if isinstance(gateway, dict) else {}
    names = ('read_bytes', 'publish_json', 'publish_bytes', 'restore_bytes', 'remove_dir')
    values = {name: gateway.get(name) for name in names}
    if not all(callable(value) for value in values.values()):
        raise TypeError('视频提示词导入需要 L3 注入发布网关')
    return values


@_publication_result
def stage_import(studio, sid, text, *, gateway=None):
    """原子暂存手工导入提示词，不提前修改分镜索引。"""
    writers = _import_gateway(gateway)
    sid = str(sid)
    text = str(text).strip()
    if not text or len(text) > 1500:
        return UserError('单镜头提示词须为 1–1500 字')
    episode = read(Path(studio.episode_path))
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        return UserError('镜头不存在：' + sid)
    folder = Path(studio.media_dir) / 'video_prompts'
    target = folder / (sid + '.json')
    previous = writers['read_bytes'](target) if target.is_file() else None
    backup = dated_path(folder / '历史版本', sid, '.json') if previous is not None else None
    record = {'shot_id': sid, 'source_signature': fingerprint(shot),
              'video_prompt': text, 'provider': 'import'}
    try:
        if backup is not None:
            writers['publish_bytes'](backup, previous)
        writers['publish_json'](target, record)
    except Exception:
        if backup is not None:
            writers['restore_bytes'](backup, None)
            writers['remove_dir'](backup.parent)
        writers['restore_bytes'](target, previous)
        raise
    return success(copy.deepcopy(record))
