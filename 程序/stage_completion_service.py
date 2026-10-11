"""无界面的阶段成果核验服务。"""
from pathlib import Path
import math

import pet_bus


def media_output_folders(root, stage):
    """返回媒体阶段的成果目录与允许扩展名。"""
    from stage_path_service import read_dirs
    if stage == 'audio':
        return tuple(folder / '音频' for folder in read_dirs(root,'audio')), {'.mp3', '.wav', '.m4a', '.aac'}
    if stage == 'edit':
        return (*read_dirs(root, 'edit'), *(folder / '导出成片' for folder in read_dirs(root,'delivery'))), {'.mp4', '.mov', '.mkv'}
    if stage == 'delivery':
        return read_dirs(root,'delivery'), {'.mp4', '.mov', '.mkv'}
    return (), set()


def media_scope(root):
    """当前已采用分镜及内容版本；切集和改稿均使旧确认失效。"""
    from agent.core import file_hash, read
    from storyboard_adoption_contract import adopted, prefs, resolve_source
    root = Path(root).resolve()
    sources = adopted(root)
    selected = prefs(root).get('frame_json')
    source = resolve_source(root, selected) if selected else (sources[0] if len(sources) == 1 else None)
    if source is None or source not in sources:
        raise ValueError('请先选择当前已采用的分镜，再确认本集成果')
    data = read(source)
    if not isinstance(data, dict) or not data.get('shots'):
        raise ValueError('当前分镜没有可核验的镜头')
    return {'project': str(root), 'source': source.relative_to(root).as_posix(),
            'source_sha256': file_hash(source), 'episode': str(data.get('episode_id') or data.get('id') or source.stem)}


def media_manifest_path(root, stage, scope):
    from agent.core import fingerprint
    from stage_path_service import write_dir
    if stage not in ('audio', 'edit', 'delivery'):
        raise ValueError('不支持的媒体成果阶段')
    return write_dir(root, stage) / '成果确认' / (fingerprint(scope['source'])[:24] + '.json')


def _media_path(root, stage, value):
    root = Path(root).resolve()
    path = Path(value)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    folders, suffixes = media_output_folders(root, stage)
    if (not path.is_relative_to(root) or not any(path.is_relative_to(folder.resolve()) for folder in folders)
            or path.suffix.lower() not in suffixes or not path.is_file() or not path.stat().st_size):
        raise ValueError('请选择本项目对应阶段目录中的有效媒体文件：' + path.name)
    return path


def _technical_media(stage, data):
    """探测结果必须有真实流和有限正时长，不能把扩展名当技术验收。"""
    from agent.media import media_facts
    return media_facts('audio' if stage == 'audio' else 'video', data)


def prepare_media_completion(root, stage, paths, *, scope=None):
    """后台技术校验并冻结待审核清单；不因导入或探测成功自动完成。"""
    from agent.core import file_hash, read
    from agent.media import probe
    from platform_tools import tool_path
    root = Path(root).resolve()
    current = media_scope(root)
    if scope is not None and scope != current:
        raise ValueError('当前分镜已切换或修改，请重新选择成果')
    scope = current
    media_manifest_path(root, stage, scope)
    config = read(root / 'config.json') if (root / 'config.json').is_file() else {}
    executable = config.get('ffprobe') or tool_path('ffprobe')
    if not executable:
        raise ValueError('请先配置 FFprobe，再校验媒体成果')
    outputs = []
    for path in dict.fromkeys(_media_path(root, stage, value) for value in paths):
        digest = file_hash(path)
        validation = _technical_media(stage, probe(path, {'ffprobe': executable}))
        if file_hash(path) != digest:
            raise ValueError('校验期间成果文件发生变化，请重试')
        outputs.append({'path': path.relative_to(root).as_posix(), 'sha256': digest,
                        'size': path.stat().st_size, 'validation': validation})
    if not outputs:
        raise ValueError('请至少选择一份本阶段媒体成果；字幕或压缩包不能替代媒体')
    data = {'schema': 1, 'stage': stage, 'scope': scope, 'status': 'pending_review', 'outputs': outputs}
    _validate_media_completion(root, stage, data, require_review=False)
    return data


def _validate_media_completion(root, stage, data, *, require_review=True):
    from agent.core import file_hash
    if (not isinstance(data, dict) or data.get('schema') != 1 or data.get('stage') != stage
            or data.get('scope') != media_scope(root)):
        raise ValueError('成果确认与当前项目、集或采用分镜版本不一致，请重新校验确认')
    if require_review and (data.get('status') != 'complete' or data.get('reviewed') is not True):
        raise ValueError('媒体已校验，仍待您确认本集内容和完整性')
    outputs = data.get('outputs')
    if not isinstance(outputs, list) or not outputs:
        raise ValueError('成果清单缺少必要媒体')
    for output in outputs:
        if not isinstance(output, dict) or not isinstance(output.get('validation'), dict):
            raise ValueError('成果清单格式错误')
        path = _media_path(root, stage, output['path'])
        validation = output.get('validation') or {}
        duration = float(validation.get('duration', 0))
        if (validation.get('passed') is not True or validation.get('kind') != ('audio' if stage == 'audio' else 'video')
                or not math.isfinite(duration) or duration <= 0):
            raise ValueError('成果清单缺少有效技术校验结果')
        if path.stat().st_size != output.get('size') or file_hash(path) != output.get('sha256'):
            raise ValueError('成果文件已替换或修改，请重新校验确认：' + path.name)


def confirm_media_completion(root, stage, prepared):
    """仅显式人工确认入口调用；发布前重新核对冻结版本。"""
    from agent.core import save
    _validate_media_completion(root, stage, prepared, require_review=False)
    data = dict(prepared, status='complete', reviewed=True)
    target = media_manifest_path(root, stage, data['scope'])
    save(target, data)
    return target


def media_completion_evidence(root, stage):
    from agent.core import read
    scope = media_scope(root)
    target = media_manifest_path(root, stage, scope)
    if not target.is_file():
        return False, '已导入或生成的文件尚未确认；请点击“校验并确认本阶段成果”'
    _validate_media_completion(root, stage, read(target))
    return True, ''


def completion_evidence(root, stage, video_ready=None):
    """返回阶段是否已有可复核成果及未通过原因。"""
    try:
        root = Path(root) if root else None
    except (TypeError, ValueError):
        return False, '项目路径无效，不能确认阶段完成'
    if root is None:
        return True, ''
    if not root.is_dir():
        return False, '项目目录不存在，不能确认阶段完成'
    stage = str(stage or '')
    try:
        if stage in ('audio', 'edit', 'delivery'):
            return media_completion_evidence(root, stage)
        if stage in ('script', 'script_structure'):
            from skill_orchestrator import verified_stage_output
            ok = verified_stage_output(root, stage)
            return ok, '没有找到可读取的%s成果' % pet_bus.STAGE_NAMES.get(stage, stage)
        if stage == 'animatic':
            from animatic_service import evidence
            return evidence(root)
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
