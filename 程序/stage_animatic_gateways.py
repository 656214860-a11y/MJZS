"""L3 动画预演网关：预演发布、参考图导入、运行与确认的正式入口装配。

自 stage_execution_service 拆出；那边按原名重新导出，旧调用点与测试补丁点不变。
"""
from pathlib import Path
from project_context_factory import project_context
from stage_path_service import write_dir
from stage_publication import publish_stage_bundle
from stage_publication import publish_stage_text
import file_cache
import json
import stage_config
from stage_gate_gateways import media_import_publisher


def publish_animatic_bundle(project, artifacts, *, validate, update_index=None):
    """整包校验、原子发布、索引更新；失败时恢复成果及同包索引。"""
    from animatic_service import MANIFEST
    root = Path(project).resolve()
    folder = write_dir(root, 'animatic').resolve()
    if not folder.is_relative_to(root) or MANIFEST not in artifacts:
        raise ValueError('Animatic 发布路径或清单无效')
    payload = {}
    for name, raw in artifacts.items():
        if name == 'animatic_index.json':
            raise ValueError('Animatic 索引只允许由发布器生成')
        target = (folder / name).resolve()
        if not target.is_relative_to(folder) or target == folder:
            raise ValueError('Animatic 成果路径越界')
        payload[target] = bytes(raw)
    payload[folder / 'animatic_index.json'] = json.dumps(
        {'manifest': MANIFEST, 'files': sorted(artifacts)}, ensure_ascii=False).encode('utf-8')
    publish_stage_bundle(payload, validate, update_index or (lambda: [file_cache.published(p) for p in payload]))
    return folder / MANIFEST


def import_animatic_references(project, sources):
    from stage_path_service import shared_reference_dir
    from animatic_service import digest
    folder = shared_reference_dir(project).resolve()
    if not folder.is_relative_to(Path(project).resolve()):
        raise ValueError('共享参考图路径越界')
    artifacts = {}
    for source in sources:
        path = Path(source)
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp') or not 0 < path.stat().st_size <= 20 * 1024 * 1024:
            raise ValueError('请选择不超过 20 MB 的 PNG、JPEG 或 WebP 参考图')
        raw = path.read_bytes()
        artifacts[folder / (digest(raw) + path.suffix.lower())] = raw
    publish_stage_bundle(artifacts, lambda items: all(raw for _, raw in items),
                         lambda: [file_cache.published(p) for p in artifacts])
    return tuple(artifacts)


def run_animatic(project, source, references, audio=None, settings=None):
    import tempfile
    from agent.core import save_bytes
    import stage_parallel
    from animatic_service import build_bundle, validate_bundle
    from platform_tools import tool_path
    settings = dict(settings or {})
    settings['retry_attempts'] = stage_parallel.retry_attempts('animatic')
    config = file_cache.read_json(Path(project) / 'config.json') if (Path(project) / 'config.json').is_file() else {}
    for tool in ('ffmpeg', 'ffprobe'):
        settings[tool] = settings.get(tool) or config.get(tool) or tool_path(tool)
        if not settings[tool]:
            raise ValueError('请在运行环境配置 ' + tool)
    gate = stage_parallel.evaluate(project, 'animatic')
    if gate and not gate['ok']:
        raise ValueError(stage_parallel.blocked_text(gate))
    from storyboard_selection import adopted
    if Path(source).resolve() not in {Path(path).resolve() for path in adopted(project)}:
        raise ValueError('请选择已采用的本项目分镜初稿')
    from comfy_runtime import wait_comfy
    wait_comfy(settings.get('url', 'http://127.0.0.1:8188'), timeout=settings.get('readiness_timeout', 45))
    work_root = write_dir(project, 'animatic') / '.work'
    work_root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='run-', dir=work_root))

    def batches(groups, worker):
        results = stage_parallel.parallel_map('animatic', groups, worker)
        for _group, _result, error in results:
            if error:
                raise error
        return [result for _group, result, _error in results]

    def publish(artifacts):
        # Media has been probed and decoded in the temporary workspace.
        if not validate_bundle(artifacts):
            raise ValueError('Animatic 清单与媒体不一致，本次不发布')
        return publish_animatic_bundle(project, artifacts, validate=lambda items: all(raw for _, raw in items))

    return build_bundle(project_context(project), source, references, audio, settings,
                        publish=publish, write_temporary=save_bytes, run_batches=batches, workspace=workspace,
                        spec=animatic_preview_spec(project))


def confirm_animatic(project, *, rhythm, duration, dialogue_sync):
    from copy import deepcopy
    from animatic_service import MANIFEST, evidence
    if not all(value is True for value in (rhythm, duration, dialogue_sync)):
        raise ValueError('节奏、时长与对白同步必须全部确认')
    ok, reason = evidence(project, require_confirmation=False)
    if not ok:
        raise ValueError(reason)
    path = write_dir(project, 'animatic') / MANIFEST
    data = deepcopy(file_cache.read_json(path))
    data['confirmed'] = dict(rhythm=True, duration=True, dialogue_sync=True)
    publish_stage_text(path, json.dumps(data, ensure_ascii=False, indent=2),
                       lambda text: bool(json.loads(text)['shots']), file_cache.published)
    return path


def animatic_reference_paths(project):
    from stage_path_service import shared_reference_read_dirs
    return tuple(dict.fromkeys(path for folder in shared_reference_read_dirs(project) if folder.is_dir()
                               for path in sorted(folder.rglob('*'))
                               if path.is_file() and path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')))


def import_animatic_audio(project, source):
    from audio_import_service import import_audio
    return import_audio(project, source, publish=media_import_publisher(project, 'audio'), stage='animatic')


def animatic_video(project):
    from animatic_service import MANIFEST, evidence
    ok, reason = evidence(project, require_confirmation=False)
    if not ok:
        raise ValueError(reason)
    folder = write_dir(project, 'animatic')
    return folder / file_cache.read_json(folder / MANIFEST)['video']


def generate_animatic_reference(project, prompt, model, settings=None):
    """本地草图准备与发布，复用 ComfyUI，不进入正式资产登记。"""
    import tempfile
    from animatic_service import prepare_reference
    from comfy_runtime import wait_comfy
    settings = dict(settings or {})
    wait_comfy(settings.get('url', 'http://127.0.0.1:8188'), timeout=settings.get('readiness_timeout', 45))
    work_root = write_dir(project, 'animatic') / '.work'
    work_root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='reference-', dir=work_root))
    return prepare_reference(workspace, prompt, model, settings,
                             publish=lambda paths: import_animatic_references(project, paths))


def animatic_preview_spec(project):
    """预演低清规格：画幅跟项目制作锁，分辨率与帧率保持低配；与正式交付规格同源。"""
    import stage_config
    from script_contract import preview_spec
    return preview_spec(stage_config.workflow_lock(Path(project)))
