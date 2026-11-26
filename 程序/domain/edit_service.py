"""无人值守自动粗剪的无界面派发决策。"""
from pathlib import Path
from functools import wraps
import logging
from contract.service_contract import SystemError, success
from contract.project_context import ProjectContext


def _project_root(project=None, *, context=None):
    if context is None:
        return Path(project).resolve()
    if not isinstance(context, ProjectContext):
        raise TypeError('剪辑清单需要由 L3 注入 ProjectContext。')
    root = context.root.resolve()
    if project is not None and Path(project).resolve() != root:
        raise ValueError('项目路径与注入的 ProjectContext 不一致。')
    return root


def _write_result(function):
    @wraps(function)
    def run(*args, **kwargs):
        try:
            return success(function(*args, **kwargs))
        except OSError:
            logging.getLogger('edit_service').exception('剪辑记录保存失败')
            return SystemError('剪辑记录保存失败，请检查文件权限和磁盘空间。')
    return run


CHECKLIST_NAME = '剪辑优化清单.md'
AUTOMATIC_ASSEMBLE_MARKER_NAME = '自动粗剪.json'


@_write_result
def save_editing_checklist(project, text, *, publish=None, context=None):
    """发布用户维护的剪辑优化清单；正式发布器必须由 L3 注入。"""
    if not callable(publish):
        raise TypeError('剪辑优化清单需要由 L3 注入发布器。')
    from contract.project_stages import editing
    target = editing(_project_root(project, context=context)) / CHECKLIST_NAME
    return publish(target, str(text or ''))


@_write_result
def save_automatic_assemble_marker(target, digest, master, completed_at, *, publish):
    """登记一次已完成的自动粗剪；正式发布器必须由 L3 注入。"""
    if not callable(publish):
        raise TypeError('自动粗剪标记需要由 L3 注入发布器。')
    target = Path(target)
    publish(target, {'digest': digest, 'master': str(master), 'at': completed_at})
    return target


def automatic_assemble_decision(signature, digest, previous_signature, completed_marker):
    """决定自动粗剪应等待、跳过已完成成果，还是启动一次拼接。"""
    if signature == previous_signature:
        return {'action': 'skip', 'signature': signature}
    if digest is None:
        return {'action': 'wait', 'signature': signature}
    if isinstance(completed_marker, dict) and completed_marker.get('digest') == digest:
        return {'action': 'complete', 'signature': signature}
    return {'action': 'dispatch', 'signature': signature}


def assemble_image_timeline(images, durations, audio, destination, *, ffmpeg, ffprobe, write_temporary, run=None, spec=None):
    """仅在调用方暂存区合成图片时间线；不登记正式视频或绕过 L3 发布器。"""
    import json
    import math
    from contract.platform_tools import run_process
    execute = run or run_process
    if not images or len(images) != len(durations):
        raise ValueError('预演镜头与时长数量不一致')
    if any(not math.isfinite(float(value)) or not 0 < float(value) <= 600 for value in durations):
        raise ValueError('每镜时长必须在 0 到 600 秒之间')
    destination = Path(destination)
    motions = spec.get('shot_motions') if isinstance(spec, dict) else None
    segments = []
    for index, (source, seconds) in enumerate(zip(images, durations)):
        segment = destination.parent / f'segment_{index:04d}.mp4'
        if motions is not None:
            motion = motions[index] if index < len(motions) else 'static'
            vf = segment_filter(spec, seconds=seconds, motion=motion)
        else:
            vf = preview_filter(spec)
        execute([str(ffmpeg), '-nostdin', '-y', '-v', 'error', '-loop', '1', '-i', str(source),
                 '-t', str(seconds), '-vf', vf,
                 '-r', str(preview_fps(spec)),
                 '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(segment)],
                check=True, capture_output=True, timeout=600)
        segments.append(segment.name)
    listing = destination.parent / 'animatic_concat.txt'
    write_temporary(listing, ''.join("file '" + name + "'\n" for name in segments).encode('utf-8'))
    execute([str(ffmpeg), '-nostdin', '-y', '-v', 'error', '-f', 'concat', '-safe', '1',
             '-i', str(listing), '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0',
             '-af', 'apad', '-t', str(sum(float(v) for v in durations)),
             '-c:v', 'copy', '-c:a', 'aac', '-movflags', '+faststart', str(destination)],
            check=True, capture_output=True, timeout=600)
    probe = execute([str(ffprobe), '-v', 'error', '-show_streams', '-show_format', '-of', 'json',
                     str(destination)], check=True, capture_output=True, timeout=30)
    info = json.loads(probe.stdout)
    kinds = {item.get('codec_type') for item in info.get('streams', [])}
    actual = float(info.get('format', {}).get('duration', 0))
    if not {'video', 'audio'} <= kinds or not math.isfinite(actual) or abs(actual - sum(map(float, durations))) > 1:
        raise ValueError('Animatic 视频、音频或时长核验失败')
    execute([str(ffmpeg), '-nostdin', '-v', 'error', '-xerror', '-i', str(destination),
             '-f', 'null', '-'], check=True, capture_output=True, timeout=600)
    return destination


def _resolved_spec(spec=None):
    from contract.script_contract import preview_spec
    base = preview_spec()
    if isinstance(spec, dict):
        return {**base, **spec}
    return base


def preview_filter(spec=None):
    """预演只降分辨率与帧率，画幅仍跟项目；不给规格就回到历史的 1280x720。"""
    from contract.script_contract import output_filter
    return output_filter(_resolved_spec(spec))


def preview_fps(spec=None):
    """预演帧率：不给规格时是 24。"""
    return _resolved_spec(spec)['fps']


def segment_filter(spec=None, *, seconds=0, motion='static'):
    """REQ-S04-104：按运镜类型生成单镜 FFmpeg 滤镜串；静态或无效时长回退 preview_filter。"""
    import math
    resolved = _resolved_spec(spec)
    base = preview_filter(resolved)
    try:
        duration = float(seconds)
    except (TypeError, ValueError):
        return base
    if not math.isfinite(duration) or duration <= 0 or motion == 'static':
        return base
    fps = resolved['fps']
    width = int(resolved['width'])
    height = int(resolved['height'])
    frames = max(1, int(round(duration * float(fps))))
    span = max(1, frames - 1)
    expressions = {
        'zoom_in': "z='min(1.15,1+0.15*on/%d)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'" % span,
        'zoom_out': "z='max(1.0,1.15-0.15*on/%d)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'" % span,
        'pan_left': "z='1.12':x='(iw-iw/zoom)*(1-on/%d)':y='ih/2-(ih/zoom/2)'" % span,
        'pan_right': "z='1.12':x='(iw-iw/zoom)*(on/%d)':y='ih/2-(ih/zoom/2)'" % span,
    }
    expr = expressions.get(motion)
    if expr is None:
        return base
    return '%s,zoompan=%s:d=%d:s=%dx%d:fps=%s,setsar=1,format=yuv420p' % (
        base, expr, frames, width, height, fps)


def render_mixed_audio(output_path, total_seconds, *, ffmpeg, run=None,
                       mix_command=None, **tracks):
    """仅在调用方暂存区混出整条临时音轨；混音命令由 L3 注入，本模块不感知三轨拼装。

    ``tracks`` 透传注入命令的轨道参数（如 full_track／dialogue_clips／music）。
    """
    if not callable(mix_command):
        raise TypeError('预演混音命令需要由 L3 注入。')
    from contract.platform_tools import run_process
    execute = run or run_process
    output_path = Path(output_path)
    command = mix_command(output_path, total_seconds, ffmpeg=ffmpeg, **tracks)
    execute([str(part) for part in command], check=True, capture_output=True, timeout=600)
    return output_path
