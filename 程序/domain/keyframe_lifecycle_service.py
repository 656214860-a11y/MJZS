"""Transactional persistence for user-visible keyframe lifecycle actions."""
import re
from functools import wraps
from pathlib import Path

from contract.service_contract import SystemError, UserError, success


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
    from storage_maintenance import recycle_paths, restore_latest_recycled_path
    if not recycle_paths(base, (path,), '删除首帧'):
        raise OSError('首帧未能安全移入项目回收站')
    previous = dict(shot)
    try:
        shot['frame_deleted'] = True
        publish(source, episode)
    except Exception:
        shot.clear()
        shot.update(previous)
        restore_latest_recycled_path(base, path)
        raise
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
    dest = (frames / (sid + '.png')).resolve()
    if not dest.is_relative_to(frames):
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
    from storage_maintenance import recycle_paths, restore_latest_recycled_child
    restored = restore_latest_recycled_child(base, frames, sid, ('.png',))
    if restored != [dest] or not dest.is_file():
        raise OSError('首帧未能安全从回收站恢复')
    previous = dict(shot)
    try:
        shot['frame'] = dest.relative_to(base).as_posix()
        shot.pop('frame_deleted', None)
        publish(source, episode)
    except Exception:
        shot.clear()
        shot.update(previous)
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
    from file_cache import remove_temporary_file
    from storage_maintenance import recycle_paths, restore_latest_recycled_path
    previous = dict(shot)
    replaced = dest.is_file()
    if replaced and not recycle_paths(base, (dest,), '替换首帧'):
        raise OSError('原首帧未能安全移入项目回收站')
    installed = False
    try:
        def update_index(_target):
            shot['frame'] = dest.relative_to(base).as_posix()
            shot.pop('frame_deleted', None)
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
    return dest
