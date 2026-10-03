"""Transactional persistence for user-visible local-video lifecycle actions."""
from pathlib import Path
from functools import wraps
import logging
from service_contract import SystemError, UserError, success

from agent.core import read


UNCERTAIN_STATES = frozenset(('queued', 'running', 'submitting', 'unknown', 'succeeded'))
LOGGER = logging.getLogger(__name__)


def _lifecycle_result(operation):
    @wraps(operation)
    def run(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except OSError:
            LOGGER.exception('视频生命周期保存失败')
            return SystemError('视频设置保存失败，请检查文件权限和磁盘空间。')
    return run


def _require_gateway(gateway):
    """L2 只接受 L3 注入的原子发布器。"""
    if not isinstance(gateway, dict) or not callable(gateway.get('publish_json')):
        raise TypeError('视频生命周期发布必须由 L3 注入 gateway')
    return gateway['publish_json']


@_lifecycle_result
def mark_video_deleted(source, sid, versions, *, gateway=None):
    """Mark one video shot deleted after its jobs are known settled.

    Historical files and task records remain untouched.  If publishing the episode
    fails, the caller's in-memory record is restored before the error is raised.
    """
    publish_json = _require_gateway(gateway)
    source = Path(source).resolve()
    sid = str(sid or '').strip()
    if not sid:
        return UserError('请选择要删除的镜头')
    if any(item.get('state') in UNCERTAIN_STATES for item in versions or ()):
        return UserError('此镜头仍有未完成或结果不确定的任务，请先查询并取回结果')
    episode = read(source)
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        return UserError('镜头已被其他操作移除，请重新打开本地视频')
    previous = dict(shot)
    try:
        shot['video_deleted'] = True
        publish_json(source, episode)
    except Exception:
        shot.clear()
        shot.update(previous)
        raise
    return success(episode)


@_lifecycle_result
def save_video_options(source, sid, selected, generate_audio, is_local, *, gateway=None):
    """Persist one shot's asset and audio options without submitting or uploading.

    The UI owns controls and refreshes; this service owns the episode mutation and
    atomic publish.  A failed publish restores the loaded record before propagating.
    """
    publish_json = _require_gateway(gateway)
    source = Path(source).resolve()
    sid = str(sid or '').strip()
    if not sid:
        return UserError('请选择要保存选项的镜头')
    selected = list(selected or ())
    episode = read(source)
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        return UserError('镜头已被其他操作移除，请重新打开视频页面')
    previous = dict(shot)
    try:
        if is_local:
            shot['local_asset_ids'] = selected
            shot['generate_audio'] = bool(generate_audio)
        else:
            shot.update(upload_assets=bool(selected), generate_audio=bool(generate_audio),
                        upload_asset_ids=selected, checkbox_defaults_version=1)
        publish_json(source, episode)
    except Exception:
        shot.clear()
        shot.update(previous)
        raise
    return success(episode)


@_lifecycle_result
def save_white_model_upload(source, sid, enabled, *, gateway=None):
    """Persist one shot's white-model upload choice without uploading media.

    The UI remains responsible for readiness and submission guards.  This service
    owns the episode mutation and restores the loaded record when atomic publish
    fails.
    """
    publish_json = _require_gateway(gateway)
    source = Path(source).resolve()
    sid = str(sid or '').strip()
    if not sid:
        return UserError('请选择要设置白模上传的镜头')
    episode = read(source)
    shot = next((item for item in episode.get('shots', ()) if item.get('id') == sid), None)
    if shot is None:
        return UserError('镜头已被其他操作移除，请重新打开视频页面')
    previous = dict(shot)
    try:
        shot['upload_white_model'] = bool(enabled)
        publish_json(source, episode)
    except Exception:
        shot.clear()
        shot.update(previous)
        raise
    return success(episode)
