"""Transactional persistence for user-visible keyframe lifecycle actions."""
import re
import sqlite3
import uuid
from functools import wraps
from pathlib import Path

from contract.infra_errors import ConfigError
from contract.service_contract import SystemError, UserError, success


def _index_register(base, path):
    """Best-effort artifact-index registration; the index is rebuildable (L1-H4)."""
    try:
        from infra.artifact_index import open_index
        with open_index(base) as index:
            return index.register(path, stage='keyframe', kind='image')
    except (OSError, sqlite3.Error, ConfigError):
        return None


def _index_recycled(base, artifact_id):
    if artifact_id is None:
        return
    try:
        from infra.artifact_index import RECYCLED, open_index
        with open_index(base) as index:
            index.set_state(artifact_id, RECYCLED)
    except (OSError, sqlite3.Error, ConfigError):
        return


def _lifecycle_result(operation):
    """把可预期的首帧业务失败收敛为 L0 服务结果。"""
    @wraps(operation)
    def wrapped(*args, **kwargs):
        try:
            return success(operation(*args, **kwargs))
        except ValueError as exc:
            return UserError(str(exc))
        except OSError as exc:
            return SystemError('首帧操作未完成，请稍后重试。', data={'cause': str(exc)})
    return wrapped


@_lifecycle_result
def delete_keyframe(base, source, episode, shot, *, publish=None):
    """Recycle one frame and persist its deleted state, restoring it on save failure."""
    base = Path(base).resolve()
    source = Path(source or base / 'episode.json').resolve()
    sid = str(shot.get('id', ''))
    if not re.fullmatch(r'(?:EP\d+_)?SH\d+', sid):
        raise ValueError('镜头编号格式不正确')
    path = (base / shot.get('frame', '')).resolve()
    frames = (base / 'frames').resolve()
    if not path.is_relative_to(frames):
        raise ValueError('仅允许删除所选JSON目录下frames中的首帧')
    if not path.is_file():
        raise ValueError('首帧已不存在，请刷新列表')
    if any(item.get('id') != sid and (base / item.get('frame', '')).resolve() == path
           for item in episode.get('shots', ())):
        raise ValueError('其他镜头也在使用此图片，请先替换它们的首帧')
    if not callable(publish):
        raise TypeError('首帧状态需要由 L3 注入发布器。')
    from infra.storage_maintenance import recycle_base, recycle_paths, restore_recycle_batch
    aid = _index_register(base, path)
    records = recycle_paths(base, (path,), '删除首帧')
    if not records:
        raise OSError('首帧未能安全移入项目回收站')
    batch_name = (base / records[0]['recycle_path']).relative_to(recycle_base(base)).parts[0]
    previous = dict(shot)
    try:
        shot['frame_deleted'] = True
        shot['frame_recycle_batch'] = batch_name
        publish(source, episode)
    except Exception:
        shot.clear()
        shot.update(previous)
        restore_recycle_batch(base, recycle_base(base) / batch_name, sources=(records[0]['source'],))
        raise
    _index_recycled(base, aid)
    return path



@_lifecycle_result
def restore_keyframe(base, source, episode, shot, *, publish=None):
    """Restore the latest recycled frame and publish its episode state transactionally.

    New deletions are recovered from the project recycle service; the storage helper also
    retains read-only compatibility with the legacy ``frames/历史版本`` directory.
    """
    base = Path(base).resolve()
    source = Path(source or base / 'episode.json').resolve()
    sid = str(shot.get('id', ''))
    if not re.fullmatch(r'(?:EP\d+_)?SH\d+', sid):
        raise ValueError('镜头编号格式不正确')
    frames = (base / 'frames').resolve()
    dest = (base / (shot.get('frame') or ('frames/' + sid + '.png'))).resolve()
    if not dest.is_relative_to(frames) or dest.suffix.lower() != '.png':
        raise ValueError('恢复目标超出项目')
    if not shot.get('frame_deleted') and dest.is_file():
        raise ValueError('此镜头已有首帧，无需恢复')
    if dest.exists():
        raise ValueError('同名首帧已存在，请先导入确认，避免覆盖')
    if any(item.get('id') != sid and (base / item.get('frame', '')).resolve() == dest
           for item in episode.get('shots', ())):
        raise ValueError('其他镜头已关联同名图片')
    if not callable(publish):
        raise TypeError('首帧状态需要由 L3 注入发布器。')
    from infra.storage_maintenance import (recycle_base, recycle_paths, restore_latest_recycled_child,
                                          restore_latest_recycled_path, restore_recycle_batch)
    previous = dict(shot)
    relative = dest.relative_to(base).as_posix()
    def publish_restored():
        shot['frame'] = relative
        shot.pop('frame_deleted', None)
        shot.pop('frame_recycle_batch', None)
        publish(source, episode)
    batch = previous.get('frame_recycle_batch')
    restored = []
    try:
        if batch:
            restored = restore_recycle_batch(base, recycle_base(base) / batch, (relative,),
                                             after_moves=publish_restored)
        else:
            # 旧索引没有批次号。标准名还须兼容早期“历史版本”；其他名称只按原路径查找。
            if dest == frames / (sid + '.png'):
                restored = restore_latest_recycled_child(base, frames, sid, ('.png',))
            else:
                restored = restore_latest_recycled_path(base, dest)
            if restored != [dest] or not dest.is_file():
                raise OSError('首帧未能安全从回收站恢复')
            publish_restored()
    except Exception:
        shot.clear()
        shot.update(previous)
        if restored and not batch:
            recycle_paths(base, (dest,), '恢复首帧失败回收')
        raise
    return dest



@_lifecycle_result
def replace_keyframe(base, source, episode, shot, data, *, publish=None, publish_episode=None):
    """Atomically replace one frame and publish its episode reference after success."""
    base = Path(base).resolve()
    source = Path(source or base / 'episode.json').resolve()
    sid = str(shot.get('id', ''))
    raw = bytes(data)
    if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('请选择PNG图片')
    if not re.fullmatch(r'(?:EP\d+_)?SH\d+', sid):
        raise ValueError('镜头编号格式不正确')
    frames = (base / 'frames').resolve()
    dest = (frames / (sid + '.png')).resolve()
    if not dest.is_relative_to(frames):
        raise ValueError('首帧路径超出当前项目')
    if any(item.get('id') != sid and (base / item.get('frame', '')).resolve() == dest
           for item in episode.get('shots', ())):
        raise ValueError('其他镜头正在使用这个文件名，请先修正其图片关联')
    if not callable(publish) or not callable(publish_episode):
        raise TypeError('首帧成果需要由 L3 注入图片与索引发布器。')
    from domain.keyframe_evidence import make_evidence
    evidence = make_evidence(source, episode, shot, raw)
    from infra.file_cache import remove_temporary_file
    from infra.storage_maintenance import recycle_paths, restore_latest_recycled_path
    previous = dict(shot)
    replaced = dest.is_file()
    if replaced and not recycle_paths(base, (dest,), '替换首帧'):
        raise OSError('原首帧未能安全移入项目回收站')
    installed = False
    try:
        def update_index(_target):
            shot['frame'] = dest.relative_to(base).as_posix()
            shot.pop('frame_deleted', None)
            shot.pop('frame_recycle_batch', None)
            shot['frame_evidence'] = evidence
            publish_episode(source, episode)

        publish(dest, raw, lambda value: value.startswith(b'\x89PNG\r\n\x1a\n'), update_index)
        installed = True
    except Exception:
        shot.clear()
        shot.update(previous)
        if installed:
            remove_temporary_file(dest)
        if replaced:
            restore_latest_recycled_path(base, dest)
        raise
    _index_register(base, dest)
    from domain import domain_events
    domain_events.emit(domain_events.KEYFRAME_REPLACED, stage='keyframe', shot=sid,
                       nonce=uuid.uuid4().hex)
    return dest
