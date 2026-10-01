"""无界面的阶段成果核验服务。"""
from pathlib import Path

import pet_bus


def media_output_folders(root, stage):
    """返回媒体阶段的成果目录与允许扩展名。"""
    from project_stages import audio, delivery, exports
    if stage == 'audio':
        return (audio(root),), {'.mp3', '.wav', '.m4a', '.aac', '.srt', '.ass'}
    if stage == 'edit':
        return (exports(root),), {'.mp4', '.mov', '.mkv'}
    if stage == 'delivery':
        return (delivery(root),), {'.mp4', '.mov', '.mkv', '.zip'}
    return (), set()


def completion_evidence(root, stage, video_ready=None):
    """返回阶段是否已有可复核成果及未通过原因。"""
    try:
        root = Path(root) if root else None
    except (TypeError, ValueError):
        root = None
    if root is None or not root.is_dir():
        return True, ''
    stage = str(stage or '')
    try:
        if stage in ('script', 'script_structure'):
            from skill_orchestrator import verified_stage_output
            ok = verified_stage_output(root, stage)
            return ok, '没有找到可读取的%s成果' % pet_bus.STAGE_NAMES.get(stage, stage)
        if stage == 'storyboard':
            from stage_parallel import _adopted
            return bool(any(shots for _source, shots in _adopted(root))), '还没有已采用且含镜头的分镜 JSON'
        checks = {'assets': 'assets_locked', 'continuity': 'ledger_ready', 'final': 'batches_ready',
                  'keyframe': 'frames_ready', 'previs': 'previs_ready'}
        if stage in checks:
            import stage_parallel
            result = getattr(stage_parallel, checks[stage])(root)
            return bool(result.get('ok') and result.get('started')), str(result.get('detail') or '阶段成果尚未通过校验')
        if stage == 'video' and callable(video_ready):
            digest, _waiting = video_ready()
            return bool(digest), '没有全部下载、质检并验收的视频镜头'
        folders, suffixes = media_output_folders(root, stage)
        if not folders and stage in pet_bus.STAGES:
            from project_stages import stage as stage_dir
            folders = (stage_dir(root, stage),)
        for folder in folders:
            if folder.is_dir():
                for path in folder.rglob('*'):
                    if path.is_file() and path.suffix.lower() in suffixes and path.stat().st_size:
                        return True, ''
        return False, '没有找到可核验的%s成果文件' % pet_bus.STAGE_NAMES.get(stage, stage)
    except (OSError, TypeError, ValueError, KeyError, ImportError) as exc:
        return False, '成果校验失败：%s' % exc


def emit_verified_completion(root, stage, text, emit, video_ready=None, before_emit=None):
    """核验成果后才通过受控事件出口标记阶段完成。"""
    ok, detail = completion_evidence(root, stage, video_ready)
    if not ok:
        return False, detail, None
    if callable(before_emit):
        before_emit()
    return True, '', emit('stage.completed', stage=str(stage or ''), text=text)
