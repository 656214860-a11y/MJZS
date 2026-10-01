"""视频提示词的可见成果发布；界面只提交镜头编号与文本。"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from agent.core import fingerprint, read, restore_bytes, save, save_bytes
from project_naming import dated_path


def _publish_legacy_bundle(artifacts):
    """旧调用方兼容入口；正式调用方必须从上层注入统一发布器。"""
    previous = {path: path.read_bytes() if path.is_file() else None for path in artifacts}
    try:
        for path, data in artifacts.items():
            save_bytes(path, data)
    except Exception:
        for path in reversed(tuple(artifacts)):
            restore_bytes(path, previous[path])
        raise


def publish(studio, sid, text, publish_bundle=None):
    """原子发布单镜头提示词及其三个可见副本，再更新分镜索引。"""
    sid = str(sid)
    text = str(text).strip()
    if not text or len(text) > 1500:
        raise ValueError('提示词须为1–1500个字符')
    episode_path = Path(studio.episode_path)
    episode = read(episode_path)
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        raise ValueError('镜头不存在：' + sid)
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
    if publish_bundle is None:
        _publish_legacy_bundle(artifacts)
    else:
        publish_bundle(artifacts, lambda _items: True, lambda: None)
    studio.episode = episode
    return copy.deepcopy(record)


def stage_import(studio, sid, text):
    """原子暂存手工导入提示词，不提前修改分镜索引。"""
    sid = str(sid)
    text = str(text).strip()
    if not text or len(text) > 1500:
        raise ValueError('单镜头提示词须为 1–1500 字')
    episode = read(Path(studio.episode_path))
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        raise ValueError('镜头不存在：' + sid)
    folder = Path(studio.media_dir) / 'video_prompts'
    target = folder / (sid + '.json')
    previous = target.read_bytes() if target.is_file() else None
    backup = dated_path(folder / '历史版本', sid, '.json') if previous is not None else None
    record = {'shot_id': sid, 'source_signature': fingerprint(shot),
              'video_prompt': text, 'provider': 'import'}
    try:
        if backup is not None:
            save_bytes(backup, previous)
        save(target, record)
    except Exception:
        if backup is not None:
            restore_bytes(backup, None)
            try:
                backup.parent.rmdir()
            except OSError:
                pass
        restore_bytes(target, previous)
        raise
    return copy.deepcopy(record)
