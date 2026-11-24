"""L3 动画预演网关：预演发布、参考图导入、运行与确认的正式入口装配。

自 stage_execution_service 拆出；那边按原名重新导出，旧调用点与测试补丁点不变。
"""
from pathlib import Path
from orchestrator.project_context_factory import project_context
from contract.stage_path_service import write_dir
from orchestrator.stage_publication import publish_stage_bundle
from orchestrator.stage_publication import publish_stage_text
import infra.file_cache as file_cache
import json
import orchestrator.stage_config as stage_config
from orchestrator.stage_gate_gateways import media_import_publisher


def publish_animatic_bundle(project, artifacts, *, validate, update_index=None):
    """整包校验、原子发布、索引更新；失败时恢复成果及同包索引。"""
    from domain.animatic_service import MANIFEST
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
    from contract.stage_path_service import shared_reference_dir
    from domain.animatic_service import digest
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
    import orchestrator.stage_parallel as stage_parallel
    from domain.animatic_service import build_bundle, validate_bundle
    from contract.platform_tools import tool_path
    settings = dict(settings or {})
    settings['retry_attempts'] = stage_parallel.retry_attempts('animatic')
    config = file_cache.read_json(Path(project) / 'config.json') if (Path(project) / 'config.json').is_file() else {}
    for tool in ('ffmpeg', 'ffprobe'):
        settings[tool] = tool_path(tool, configured=settings.get(tool) or config.get(tool))
        if not settings[tool]:
            raise ValueError('请在运行环境配置 ' + tool)
    gate = stage_parallel.evaluate(project, 'animatic')
    if gate and not gate['ok']:
        raise ValueError(stage_parallel.blocked_text(gate))
    from orchestrator.storyboard_selection import adopted
    if Path(source).resolve() not in {Path(path).resolve() for path in adopted(project)}:
        raise ValueError('请选择已采用的本项目分镜初稿')
    from infra.comfy_runtime import open_comfy, wait_comfy
    url = settings.get('url', 'http://127.0.0.1:8188')
    try:
        wait_comfy(url, timeout=settings.get('probe_timeout', 5))
    except ValueError:
        # R3162 M2：ComfyUI 是可选高级项——未运行时尝试拉起桌面程序；找不到程序时
        # open_comfy 自带「去设置」引导文案，不再干等 45 秒超时。
        open_comfy()
        wait_comfy(url, timeout=settings.get('readiness_timeout', 45))
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
    from domain.animatic_service import MANIFEST, evidence
    if not all(value is True for value in (rhythm, duration, dialogue_sync)):
        raise ValueError('节奏、时长与对白同步必须全部确认')
    ok, reason = evidence(project, require_confirmation=False)
    if not ok:
        raise ValueError(reason)
    path = write_dir(project, 'animatic') / MANIFEST
    data = deepcopy(file_cache.read_json(path))
    data['confirmed'] = dict(rhythm=True, duration=True, dialogue_sync=True)
    # D4-d/G8：future 清单可读但拒写（确认改写同样是写入口），发一次【警告】。
    import contract.artifact_schema as artifact_schema
    import infra.broadcaster as broadcaster
    if artifact_schema.classify('animatic_manifest', data) == 'future':
        broadcaster.warn_once('artifact_future:animatic_manifest',
                              'Animatic 清单是更新版本写的产物，本版程序拒绝覆盖；请升级程序或移走该文件')
        raise ValueError('Animatic 清单是更新版本写的产物，本版程序拒绝覆盖；请升级程序或移走该文件')
    # G8：确认改写属正常写入，顺带补 schema_version（保留旧键 version）。
    data = artifact_schema.stamp('animatic_manifest', data)
    publish_stage_text(path, json.dumps(data, ensure_ascii=False, indent=2),
                       lambda text: bool(json.loads(text)['shots']), file_cache.published)
    return path


def animatic_reference_paths(project):
    from contract.stage_path_service import shared_reference_read_dirs
    return tuple(dict.fromkeys(path for folder in shared_reference_read_dirs(project) if folder.is_dir()
                               for path in sorted(folder.rglob('*'))
                               if path.is_file() and path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')))


def import_animatic_audio(project, source):
    from domain.audio_import_service import import_audio
    return import_audio(project, source, publish=media_import_publisher(project, 'audio'), stage='animatic')


def animatic_video(project):
    from domain.animatic_service import MANIFEST, evidence
    ok, reason = evidence(project, require_confirmation=False)
    if not ok:
        raise ValueError(reason)
    folder = write_dir(project, 'animatic')
    return folder / file_cache.read_json(folder / MANIFEST)['video']


def generate_animatic_reference(project, prompt, model, settings=None):
    """本地草图准备与发布，复用 ComfyUI，不进入正式资产登记。"""
    import tempfile
    from domain.animatic_service import prepare_reference
    from infra.comfy_runtime import open_comfy, wait_comfy
    settings = dict(settings or {})
    url = settings.get('url', 'http://127.0.0.1:8188')
    try:
        wait_comfy(url, timeout=settings.get('probe_timeout', 5))
    except ValueError:
        open_comfy()
        wait_comfy(url, timeout=settings.get('readiness_timeout', 45))
    work_root = write_dir(project, 'animatic') / '.work'
    work_root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='reference-', dir=work_root))
    return prepare_reference(workspace, prompt, model, settings,
                             publish=lambda paths: import_animatic_references(project, paths))


def animatic_preview_spec(project):
    """预演低清规格：画幅跟项目制作锁，分辨率与帧率保持低配；与正式交付规格同源。"""
    import orchestrator.stage_config as stage_config
    from contract.script_contract import preview_spec
    return preview_spec(stage_config.workflow_lock(Path(project)))


def animatic_reference_library(project):
    """共享参考库视图：新目录按 角色/场景/风格 归类，库根与旧目录图归未分类。"""
    from contract.stage_path_service import shared_reference_read_dirs
    from domain.animatic_references import library
    return library(shared_reference_read_dirs(project))


def import_animatic_reference_library(project, sources, *, characters=(), locations=(), category=None):
    """按文件名自动归类导入参考库；内容去重、同名编号，原子发布到对应子目录。"""
    from contract.stage_path_service import shared_reference_dir
    from domain.animatic_references import import_plan
    root = Path(project).resolve()
    folder = shared_reference_dir(root).resolve()
    if not folder.is_relative_to(root):
        raise ValueError('共享参考图路径越界')
    plan = import_plan(sources, characters=characters, locations=locations,
                       existing=animatic_reference_paths(project), category=category)
    artifacts = {}
    for relative, raw in plan.items():
        target = (folder / relative).resolve()
        if not target.is_relative_to(folder):
            raise ValueError('参考图目标路径越界')
        artifacts[target] = raw
    if not artifacts:
        return ()
    publish_stage_bundle(artifacts, lambda items: all(raw for _, raw in items),
                         lambda: [file_cache.published(p) for p in artifacts])
    return tuple(artifacts)


def refs_for_animatic_shot(project, shot):
    """按镜 characters/location 在参考库自动配图；未命中任何分类图退回未分类。"""
    from domain.animatic_references import refs_for_shot
    return refs_for_shot(shot, animatic_reference_library(project))


def reclassify_animatic_reference(project, path, category, new_name=None):
    """单张参考图改类／改名：原子写新路径，旧文件经回收站退役；源与目标都在库内。"""
    from contract.stage_path_service import shared_reference_dir
    from domain.animatic_references import CATEGORIES, IMAGE_SUFFIXES, UNCATEGORIZED
    from infra.storage_maintenance import recycle_paths
    from orchestrator.stage_publication import publish_stage_bytes
    root = Path(project).resolve()
    folder = shared_reference_dir(root).resolve()
    if not folder.is_relative_to(root):
        raise ValueError('共享参考图路径越界')
    source = Path(path).resolve()
    if not source.is_file() or not source.is_relative_to(folder):
        raise ValueError('参考图不在共享参考图目录内')
    if category not in (*CATEGORIES, UNCATEGORIZED):
        raise ValueError('参考图分类无效：' + str(category))
    name = str(new_name).strip() if new_name is not None else source.name
    if not name or Path(name).name != name or Path(name).suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError('参考图文件名无效')
    target = (folder / name if category == UNCATEGORIZED else folder / category / name).resolve()
    if not target.is_relative_to(folder):
        raise ValueError('参考图目标路径越界')
    if target == source:
        return source
    if target.exists():
        raise ValueError('目标参考图已存在')
    publish_stage_bytes(target, source.read_bytes(), lambda raw: bool(raw), file_cache.published)
    recycle_paths(root, [source], '分镜预演参考图改类')
    return target
