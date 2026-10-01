"""Transactional persistence for user-visible local-video lifecycle actions."""
from pathlib import Path

from agent.core import read, save


UNCERTAIN_STATES = frozenset(('queued', 'running', 'submitting', 'unknown', 'succeeded'))


def mark_video_deleted(source, sid, versions):
    """Mark one video shot deleted after its jobs are known settled.

    Historical files and task records remain untouched.  If publishing the episode
    fails, the caller's in-memory record is restored before the error is raised.
    """
    source = Path(source).resolve()
    sid = str(sid or '').strip()
    if not sid:
        raise ValueError('请选择要删除的镜头')
    if any(item.get('state') in UNCERTAIN_STATES for item in versions or ()):
        raise ValueError('此镜头仍有未完成或结果不确定的任务，请先查询并取回结果')
    episode = read(source)
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        raise ValueError('镜头已被其他操作移除，请重新打开本地视频')
    previous = dict(shot)
    try:
        shot['video_deleted'] = True
        save(source, episode)
    except Exception:
        shot.clear()
        shot.update(previous)
        raise
    return episode


def save_video_options(source, sid, selected, generate_audio, is_local):
    """Persist one shot's asset and audio options without submitting or uploading.

    The UI owns controls and refreshes; this service owns the episode mutation and
    atomic publish.  A failed publish restores the loaded record before propagating.
    """
    source = Path(source).resolve()
    sid = str(sid or '').strip()
    if not sid:
        raise ValueError('请选择要保存选项的镜头')
    selected = list(selected or ())
    episode = read(source)
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        raise ValueError('镜头已被其他操作移除，请重新打开视频页面')
    previous = dict(shot)
    try:
        if is_local:
            shot['local_asset_ids'] = selected
            shot['generate_audio'] = bool(generate_audio)
        else:
            shot.update(upload_assets=bool(selected), generate_audio=bool(generate_audio),
                        upload_asset_ids=selected, checkbox_defaults_version=1)
        save(source, episode)
    except Exception:
        shot.clear()
        shot.update(previous)
        raise
    return episode


def save_white_model_upload(source, sid, enabled):
    """Persist one shot's white-model upload choice without uploading media.

    The UI remains responsible for readiness and submission guards.  This service
    owns the episode mutation and restores the loaded record when atomic publish
    fails.
    """
    source = Path(source).resolve()
    sid = str(sid or '').strip()
    if not sid:
        raise ValueError('请选择要设置白模上传的镜头')
    episode = read(source)
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        raise ValueError('镜头已被其他操作移除，请重新打开视频页面')
    previous = dict(shot)
    try:
        shot['upload_white_model'] = bool(enabled)
        save(source, episode)
    except Exception:
        shot.clear()
        shot.update(previous)
        raise
    return episode
