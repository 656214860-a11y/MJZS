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


def import_animatic_audio(project, source, *, track=None):
    from domain.audio_import_service import import_audio
    return import_audio(project, source, **_animatic_audio_route(project, source, track))


def remove_animatic_audio(project, track):
    """REQ-S04-114：将整轨或背景音乐子目录下真实音频经回收站安全移除并返回路径。"""
    from domain import animatic_audio
    from infra.storage_maintenance import recycle_paths
    if track not in ('track', 'music'):
        raise ValueError('音频轨道类型无效：' + str(track))
    root = Path(project).resolve()
    target_dir = write_dir(root, 'animatic') / animatic_audio.SUBDIRS[track]
    if not target_dir.is_dir():
        return ()
    files = tuple(sorted(path for path in target_dir.iterdir() if path.is_file()))
    if not files:
        return ()
    recycle_paths(root, list(files), '移除分镜预演临时音频')
    return files


def animatic_video(project):
    from domain.animatic_service import MANIFEST, evidence
    ok, reason = evidence(project, require_confirmation=False)
    if not ok:
        raise ValueError(reason)
    folder = write_dir(project, 'animatic')
    return folder / file_cache.read_json(folder / MANIFEST)['video']


def _probe_comfy(settings):
    """探测并按需拉起本机 ComfyUI，供预演与参考草图入口共用。"""
    from infra.comfy_runtime import open_comfy, wait_comfy
    probe_timeout = settings.get('probe_timeout', 5)
    readiness_timeout = settings.get('readiness_timeout', 45)
    url = (settings.get('url')
           or 'http://127.0.0.1:8188')
    try:
        wait_comfy(url, timeout=probe_timeout)
    except ValueError:
        open_comfy()
        wait_comfy(url, timeout=readiness_timeout)


def generate_animatic_reference(project, prompt, model, settings=None):
    """本地草图准备与发布，复用 ComfyUI，不进入正式资产登记。"""
    import tempfile
    from domain.animatic_service import prepare_reference
    settings = dict(settings or {})
    _probe_comfy(settings)
    work_root = write_dir(project, 'animatic') / '.work'
    work_root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='reference-', dir=work_root))
    return prepare_reference(workspace, prompt, model, settings,
                             publish=lambda paths: import_animatic_references(project, paths))


def _animatic_audio_route(project, source, track):
    """整轨／音乐按用途落入 声音/ 对应子目录：显式 track 优先，否则按文件名归类。"""
    from domain import animatic_audio
    if track not in ('track', 'music'):
        name = Path(source).name.lower()
        track = 'music' if any(key in name for key in ('bgm', 'music', '音乐', '配乐')) else 'track'
    return {'publish': media_import_publisher(project, 'audio'), 'stage': 'animatic',
            'subdir': animatic_audio.SUBDIRS[track]}


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


def _formal_animatic_assets(project):
    """REQ-S04-113：只读读取 S05 已入库正式资产图（缺失或损坏时安全降级为空，绝不写盘）。"""
    from domain.animatic_references import formal_asset_entries
    from domain.asset_context import library_dir
    try:
        base = library_dir(Path(project).resolve())
        plan_path = base / 'assets' / '资产清单' / 'assets.json'
        reg_path = base / 'assets.json'
        plan = file_cache.read_json(plan_path) if plan_path.is_file() else {}
        registry = file_cache.read_json(reg_path) if reg_path.is_file() else {}
        return formal_asset_entries(plan, registry, base)
    except Exception:
        return {'角色': [], '场景': []}


formal_animatic_assets = _formal_animatic_assets


def refs_for_animatic_shot(project, shot):
    """REQ-S04-72/113：按编号／名称／别名优先复用 S05 正式资产图，未命中回退共享参考库。"""
    from domain.animatic_references import refs_for_shot
    return refs_for_shot(shot, animatic_reference_library(project),
                         formal_assets=_formal_animatic_assets(project))


def shot_ref_details(project, shot):
    """REQ-S04-115/113：返回单镜实际命中参考图及来源徽章列表。"""
    from domain.animatic_references import shot_ref_badges
    return shot_ref_badges(shot, animatic_reference_library(project),
                           formal_assets=_formal_animatic_assets(project))


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


# ── REQ-S04-80…91：时间线、单镜版本与重做／替换、版本化合成、锁定回写 ──────────

def _animatic_source(project, source=None):
    """时间线所属的已采用分镜：优先沿用时间线登记的来源，其次最近采用的一份。"""
    from orchestrator.storyboard_selection import adopted
    root = Path(project).resolve()
    paths = [Path(path).resolve() for path in adopted(root)]
    if source is not None:
        resolved = Path(source).resolve()
        if resolved not in paths:
            raise ValueError('请选择已采用的本项目分镜初稿')
        return resolved
    if not paths:
        raise ValueError('请先采用分镜初稿')
    from domain.animatic_timeline import TIMELINE_FILE
    try:
        timeline = file_cache.read_json(write_dir(root, 'animatic') / TIMELINE_FILE)
    except (OSError, ValueError):
        timeline = None
    recorded = timeline.get('source') if isinstance(timeline, dict) else None
    if recorded:
        candidate = (root / recorded).resolve()
        if candidate in paths:
            return candidate
    return paths[-1]


def _publish_animatic_timeline(project, timeline):
    """timeline.json 只经 L3 发布器落盘（DES-S04-23）。"""
    import contract.artifact_schema as artifact_schema
    if artifact_schema.validate('animatic_timeline', timeline):
        raise ValueError('时间线不满足 animatic_timeline 登记结构')
    target = write_dir(Path(project).resolve(), 'animatic') / 'timeline.json'
    publish_stage_text(target, json.dumps(timeline, ensure_ascii=False, indent=2),
                       lambda text: '"animatic_timeline"' in text and '"shots"' in text,
                       file_cache.published)
    return target


def _shot_dir(folder, shot_id):
    return Path(folder) / '镜头' / str(shot_id)


def _versioned_image(shot_dir, version):
    """当前选用的 v<N>.* 图；目录缺文件即返回 None（缺图才生成）。"""
    folder = Path(shot_dir)
    if not folder.is_dir():
        return None
    prefix = ('v%d.' % int(version)).lower()
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.name.lower().startswith(prefix):
            return path
    return None


def _existing_names(folder):
    folder = Path(folder)
    return [path.name for path in folder.iterdir()] if folder.is_dir() else []


def _shot_refs_relative(root, refs):
    out = []
    for path in refs or ():
        path = Path(path).resolve()
        out.append(path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path))
    return out


def _timeline_row_update(timeline, shot_id, fields):
    from copy import deepcopy
    out = deepcopy(timeline)
    for row in out.get('shots') or []:
        if isinstance(row, dict) and row.get('id') == shot_id:
            row.update(fields)
            return out
    raise ValueError('时间线没有此镜头：' + str(shot_id))


def _load_gflow_generate():
    """惰性探测并加载 infra.gflow_images.generate，模块未就绪时返回 None。"""
    import importlib.util
    import sys
    if 'infra.gflow_images' in sys.modules:
        return getattr(sys.modules['infra.gflow_images'], 'generate', None)
    if importlib.util.find_spec('infra.gflow_images') is None:
        return None
    import infra.gflow_images as gflow_images
    return getattr(gflow_images, 'generate', None)


def _resolve_gflow_settings(settings):
    """REQ-S04-101：惰性解析模型池 gflow-* 图片模型与 infra.gflow_images.generate。"""
    resolved = dict(settings)
    if not callable(resolved.get('gflow_generate')):
        generate = _load_gflow_generate()
        if not callable(generate):
            raise ValueError('请先在模型管理配置 Google Flow 账号与 gflow.exe')
        resolved['gflow_generate'] = generate
    if not isinstance(resolved.get('gflow_config'), dict) or not resolved['gflow_config']:
        import infra.model_pool as model_pool
        pool = model_pool.pool() or {}
        candidates = {
            mid: item for mid, item in pool.items()
            if isinstance(mid, str) and mid.startswith('gflow-')
            and isinstance(item, dict)
            and str(item.get('modality') or '').strip().lower() == 'image'
        }
        if not candidates:
            raise ValueError('请先在模型管理配置 Google Flow 账号与 gflow.exe')
        preferred = str(resolved.get('animatic_gflow_model') or '').strip()
        if preferred in candidates:
            selected = preferred
        elif ('gflow-' + preferred) in candidates:
            selected = 'gflow-' + preferred
        else:
            selected = next(iter(candidates))
        config = dict(candidates[selected])
        config['model'] = selected[6:]
        resolved['gflow_config'] = config
    return resolved


def _timeline_render(settings):
    """草图后端分流：适配 text_card、gflow_cli 与默认 comfy_local。"""
    from domain import animatic_service, animatic_sketch_backends
    name = settings.get('animatic_sketch_backend') or animatic_sketch_backends.DEFAULT_BACKEND
    if name == 'gflow_cli':
        resolved = _resolve_gflow_settings(settings)
        base_render = animatic_sketch_backends.create(resolved)

        def render_gflow(workspace, shot, references, run_settings=None):
            merged = dict(run_settings or {})
            if not callable(merged.get('gflow_generate')):
                merged['gflow_generate'] = resolved['gflow_generate']
            if not isinstance(merged.get('gflow_config'), dict) or not merged['gflow_config']:
                merged['gflow_config'] = resolved['gflow_config']
            return base_render(workspace, shot, references, merged)

        return render_gflow
    render = animatic_sketch_backends.create(settings)
    if name == 'comfy_local' and settings.get('comfy_client') is None:
        return animatic_service.local_sketch
    return render


def _render_single_shot(story_row, refs, settings, workspace):
    """沿用整批重试口径渲染单镜；只有 ComfyGenerationFailed 才重试。"""
    from infra.comfy_service import ComfyGenerationFailed
    render = _timeline_render(settings)
    for attempt in range(int(settings.get('retry_attempts', 0)) + 1):
        attempt_dir = Path(workspace) / ('attempt-%d' % attempt)
        attempt_dir.mkdir(parents=True, exist_ok=True)
        try:
            return render(attempt_dir, story_row, refs, settings)
        except ComfyGenerationFailed:
            if attempt == int(settings.get('retry_attempts', 0)):
                raise ValueError('镜头 ' + str(story_row['id']) + ' 生成失败且重试耗尽，请人工核查') from None


def _publish_shot_file(folder, shot_id, version, suffix, raw):
    from orchestrator.stage_publication import publish_stage_bytes
    target = _shot_dir(folder, shot_id) / ('v%d%s' % (int(version), suffix))
    publish_stage_bytes(target, raw, lambda data: bool(data), file_cache.published)
    return target


def _first_media_file(folder):
    folder = Path(folder)
    if not folder.is_dir():
        return None
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.stat().st_size:
            return path
    return None


def load_or_sync_animatic_timeline(project, source=None):
    """REQ-S04-80/85：sha 一致直接返回；S03 变化或缺失时建/重建并发布 timeline.json。"""
    from domain import animatic_timeline as timeline_model
    from domain.animatic_service import digest
    root = Path(project).resolve()
    path = _animatic_source(root, source)
    storyboard, raw, _signature = file_cache.read_stable_json_snapshot(path)
    sha = digest(raw)
    rel = path.relative_to(root).as_posix()
    target = write_dir(root, 'animatic') / timeline_model.TIMELINE_FILE
    try:
        previous = file_cache.read_json(target)
    except (OSError, ValueError):
        previous = None
    if (isinstance(previous, dict) and previous.get('source') == rel
            and previous.get('source_sha256') == sha):
        return previous
    if not isinstance(previous, dict):
        previous = None
    timeline, rebuilt = timeline_model.build(storyboard, rel, sha, previous=previous)
    _publish_animatic_timeline(root, timeline)
    if rebuilt:
        import infra.broadcaster as broadcaster
        broadcaster.warn_once('animatic_timeline:rebuilt', '分镜已更新，时间线已重建')
    return timeline


def update_animatic_shot(project, shot_id, *, seconds=None, image_version=None, note=None,
                         review_status=None):
    """REQ-S04-81/82/97/115：单镜改时长、切图版本、写批注或更新审核状态后发布时间线。"""
    from domain import animatic_timeline as timeline_model
    root = Path(project).resolve()
    timeline = load_or_sync_animatic_timeline(root)
    if image_version is not None:
        if _versioned_image(_shot_dir(write_dir(root, 'animatic'), shot_id), image_version) is None:
            raise ValueError('该图版本不存在：v%s' % image_version)
    updated = timeline
    if seconds is not None:
        updated = timeline_model.set_duration(updated, shot_id, seconds)
    if image_version is not None:
        updated = timeline_model.set_version(updated, shot_id, image_version)
    if note is not None:
        updated = timeline_model.set_note(updated, shot_id, note)
    if review_status is not None:
        updated = timeline_model.set_review_status(updated, shot_id, review_status)
    if updated != timeline:
        _publish_animatic_timeline(root, updated)
    return updated


def regenerate_animatic_shot(project, shot_id, *, settings=None):
    """REQ-S04-83：只重做单镜草图写新版本，其余镜头与时间线字段不动。"""
    import tempfile
    from domain import animatic_timeline as timeline_model
    from domain.animatic_service import shots_of
    import orchestrator.stage_parallel as stage_parallel
    root = Path(project).resolve()
    folder = write_dir(root, 'animatic')
    settings = dict(settings or {})
    settings['retry_attempts'] = stage_parallel.retry_attempts('animatic')
    timeline = load_or_sync_animatic_timeline(root)
    if not any(row.get('id') == shot_id for row in timeline['shots']):
        raise ValueError('时间线没有此镜头：' + str(shot_id))
    storyboard = file_cache.read_json(_animatic_source(root))
    story_row = next((row for row in shots_of(storyboard) if row['id'] == shot_id), None)
    if story_row is None:
        raise ValueError('分镜没有此镜头：' + str(shot_id))
    board_row = next((row for row in storyboard.get('shots', [])
                      if isinstance(row, dict) and row.get('id') == shot_id), {})
    refs = refs_for_animatic_shot(root, board_row)
    _ensure_comfy_ready(settings)
    settings.setdefault('spec', animatic_preview_spec(root))
    timeline_row = next(row for row in timeline['shots'] if row.get('id') == shot_id)
    render_shot = dict(board_row, **story_row)
    render_shot['seconds'] = timeline_row.get('seconds', story_row['seconds'])
    workspace = Path(tempfile.mkdtemp(prefix='shot-', dir=_work_root(folder)))
    image = _render_single_shot(render_shot, refs, settings, workspace)
    version = timeline_model.next_version(_existing_names(_shot_dir(folder, shot_id)))
    _publish_shot_file(folder, shot_id, version, Path(image).suffix.lower(),
                       Path(image).read_bytes())
    updated = timeline_model.set_version(timeline, shot_id, version, source='generated')
    updated = _timeline_row_update(updated, shot_id,
                                   {'references': _shot_refs_relative(root, refs)})
    _publish_animatic_timeline(root, updated)
    return updated


def regenerate_revision_shots(project, *, settings=None):
    """REQ-S04-115：仅重做标记为「需修改」的镜头，每镜重做成功后重置审核状态为 pending。"""
    from domain import animatic_timeline as timeline_model
    root = Path(project).resolve()
    timeline = load_or_sync_animatic_timeline(root)
    targets = timeline_model.needs_revision_ids(timeline)
    if not targets:
        raise ValueError('当前没有标记「需修改」的镜头')
    updated = timeline
    for shot_id in targets:
        regenerate_animatic_shot(root, shot_id, settings=settings)
        updated = update_animatic_shot(root, shot_id, review_status='pending')
    return updated


def replace_animatic_shot_image(project, shot_id, image_path):
    """REQ-S04-79/82：导入图校验后写新版本，时间线记 source='imported'。"""
    from domain import animatic_sketch_backends, animatic_timeline as timeline_model
    root = Path(project).resolve()
    folder = write_dir(root, 'animatic')
    timeline = load_or_sync_animatic_timeline(root)
    if not any(row.get('id') == shot_id for row in timeline['shots']):
        raise ValueError('时间线没有此镜头：' + str(shot_id))
    suffix, raw = animatic_sketch_backends.validate_imported_sketch(image_path)
    version = timeline_model.next_version(_existing_names(_shot_dir(folder, shot_id)))
    _publish_shot_file(folder, shot_id, version, suffix, raw)
    updated = timeline_model.set_version(timeline, shot_id, version, source='imported')
    _publish_animatic_timeline(root, updated)
    return updated


def _work_root(folder):
    work_root = Path(folder) / '.work'
    work_root.mkdir(parents=True, exist_ok=True)
    return work_root


def _timeline_audio(root, folder, timeline, board, settings, scratch):
    """三轨声音：整轨／音乐取 声音/ 目录或注入项，逐镜对白幂等 TTS，混音命令 L2 拼装。

    返回 ``(混音文件, {镜头id: 对白音频 Path})``。
    """
    from domain import animatic_audio
    from domain.animatic_audio import build_audio_mix_command
    from domain.edit_service import render_mixed_audio
    from orchestrator.stage_publication import publish_stage_bytes
    audio_root = Path(folder)
    full_track = settings.get('full_track') or _first_media_file(
        audio_root / animatic_audio.SUBDIRS['track'])
    music = settings.get('music') or _first_media_file(
        audio_root / animatic_audio.SUBDIRS['music'])
    audio_shots = [{'id': row['id'], 'seconds': row['seconds'],
                    'dialogue': board.get(row['id'], {}).get('dialogue')}
                   for row in timeline['shots']]
    use_tts = bool(settings.get('animatic_use_tts', True))
    plan = animatic_audio.plan(audio_shots, full_track=full_track, music=music, use_tts=use_tts)
    clips, clip_map = [], {}
    if plan['tts_shots']:
        from domain.tts_api import read_settings, script_signature, synthesize
        tts_settings = settings.get('tts_settings') or read_settings()
        synth = settings.get('synthesize') or synthesize
        signature_fn = settings.get('signature_fn') or script_signature
        for item in plan['tts_shots']:
            try:
                clip = animatic_audio.shot_tts(
                    {'id': item['id'], 'text': item['text']},
                    audio_root / animatic_audio.SUBDIRS['dialogue'], tts_settings,
                    synthesize=synth, signature_fn=signature_fn,
                    write_temporary=lambda path, raw: publish_stage_bytes(
                        path, raw, lambda data: bool(data), file_cache.published),
                    project=root)
            except Exception as exc:
                raise ValueError('逐镜临时配音失败，可在「声音」关闭逐镜 TTS 先静音出片或配置语音：'
                                 + str(exc)) from None
            clips.append({'path': clip, 'start_ms': int(round(item['start_seconds'] * 1000))})
            clip_map[item['id']] = clip
    total = sum(float(row['seconds']) for row in timeline['shots'])
    mixed = render_mixed_audio(Path(scratch) / 'animatic_audio.wav', total,
                               ffmpeg=settings['ffmpeg'], run=settings.get('run'),
                               mix_command=build_audio_mix_command,
                               full_track=plan['full_track'], dialogue_clips=clips,
                               music=plan['music'])
    return mixed, clip_map


def _measure_audio_seconds(clip, ffprobe, probe_fn=None):
    """实测单段音频秒数；无法读取或无效时长返回 None，不阻断合成。"""
    import math
    if clip is None:
        return None
    try:
        if callable(probe_fn):
            value = float(probe_fn(clip))
        else:
            from agent.media import probe
            data = probe(str(clip), {'ffprobe': ffprobe})
            raw = (data.get('format') or {}).get('duration')
            if raw is None:
                return None
            value = float(raw)
    except (OSError, RuntimeError, ValueError, TypeError):
        return None
    return round(value, 3) if math.isfinite(value) and value > 0 else None


def _probe_dialogue_seconds(clip_map, settings):
    """REQ-S04-105：在合成后台实测各镜对白秒数，消除 Tk 主线程同步探测。"""
    if not clip_map:
        return {}
    probe_fn = settings.get('probe_duration')
    ffprobe = settings.get('ffprobe')
    return {sid: _measure_audio_seconds(clip, ffprobe, probe_fn)
            for sid, clip in clip_map.items()}


def _overlay_frame(image_path, destination, *, shot_id, seconds, start_seconds, dialogue=''):
    """REQ-S04-103：L3 注入的暂存烧录钩子；非图片桩字节优雅退回原路径。"""
    from PIL import UnidentifiedImageError
    from domain.animatic_sketch_backends import render_overlay_frame
    try:
        return render_overlay_frame(image_path, destination, shot_id=shot_id,
                                    seconds=seconds, start_seconds=start_seconds,
                                    dialogue=dialogue)
    except UnidentifiedImageError:
        return Path(image_path)


def _compose_timeline_rows(root, timeline, shot_versions, existing_images,
                           shot_references, clip_map, *, dialogue_durations=None):
    """合成成功后把图版本、来源、参考图、对白音频与实测对白秒数写回时间线副本。"""
    from copy import deepcopy
    out = deepcopy(timeline)
    durations = dialogue_durations or {}
    for row in out.get('shots') or []:
        sid = row.get('id')
        if sid in shot_versions:
            row['image_version'] = shot_versions[sid]
            if sid not in existing_images:
                row['source'] = 'generated'
        row['references'] = _shot_refs_relative(root, shot_references.get(sid, ()))
        clip = clip_map.get(sid)
        row['dialogue_audio'] = (
            Path(clip).resolve().relative_to(root).as_posix()
            if clip is not None and Path(clip).resolve().is_relative_to(root) else None)
        row['dialogue_seconds'] = durations.get(sid) if clip is not None else None
    return out


def _ensure_comfy_ready(settings):
    """选择 comfy_local 且未注入客户端时探测/拉起本地 ComfyUI。"""
    from domain import animatic_sketch_backends
    backend = settings.get('animatic_sketch_backend') or animatic_sketch_backends.DEFAULT_BACKEND
    if backend != 'comfy_local' or settings.get('comfy_client') is not None:
        return
    _probe_comfy(settings)


def run_animatic_timeline(project, source=None, *, settings=None):
    """REQ-S04-80…84/103…105：参考库配图＋三轨混音＋暂存烧录/2D运镜＋版本化视频＋清单发布。"""
    import tempfile
    from agent.core import save_bytes
    import orchestrator.stage_parallel as stage_parallel
    from domain import animatic_sketch_backends, animatic_timeline as timeline_model
    from domain.animatic_service import build_bundle, validate_bundle
    from contract.platform_tools import tool_path
    root = Path(project).resolve()
    folder = write_dir(root, 'animatic')
    settings = dict(settings or {})
    settings['retry_attempts'] = stage_parallel.retry_attempts('animatic')
    config = file_cache.read_json(root / 'config.json') if (root / 'config.json').is_file() else {}
    for tool in ('ffmpeg', 'ffprobe'):
        settings[tool] = tool_path(tool, configured=settings.get(tool) or config.get(tool))
        if not settings[tool]:
            raise ValueError('请在运行环境配置 ' + tool)
    gate = stage_parallel.evaluate(project, 'animatic')
    if gate and not gate['ok']:
        raise ValueError(stage_parallel.blocked_text(gate))
    path = _animatic_source(root, source)
    timeline = load_or_sync_animatic_timeline(root, path)
    storyboard, _raw, _signature = file_cache.read_stable_json_snapshot(path)
    board = {str(row.get('id')): row for row in storyboard.get('shots', [])
             if isinstance(row, dict)}
    shot_versions, existing_images, shot_references = {}, {}, {}
    for row in timeline['shots']:
        sid = row['id']
        current = _versioned_image(_shot_dir(folder, sid), int(row.get('image_version') or 0))
        if current is not None:
            existing_images[sid] = current
            shot_versions[sid] = int(row['image_version'])
        else:
            shot_versions[sid] = timeline_model.next_version(
                _existing_names(_shot_dir(folder, sid)))
        shot_references[sid] = refs_for_animatic_shot(root, board.get(sid, {}))
    if len(existing_images) < len(timeline['shots']):
        _ensure_comfy_ready(settings)
    workspace = Path(tempfile.mkdtemp(prefix='run-', dir=_work_root(folder)))
    audio, clip_map = _timeline_audio(root, folder, timeline, board, settings, workspace)
    dialogue_durations = _probe_dialogue_seconds(clip_map, settings)
    preview_spec = animatic_preview_spec(root)
    settings.setdefault('spec', preview_spec)
    settings.setdefault('overlay_frame', _overlay_frame)
    settings['shot_references'] = shot_references
    settings['allow_empty_references'] = True
    settings['existing_images'] = existing_images
    settings['shot_versions'] = shot_versions
    settings['timeline_durations'] = {row['id']: int(row['seconds'])
                                     for row in timeline['shots']}
    settings['video_relpath'] = timeline_model.next_video_name(_existing_names(folder / '版本'))
    settings['version_tag'] = Path(settings['video_relpath']).stem
    settings['timeline_sha256'] = file_cache.file_digest(
        folder / timeline_model.TIMELINE_FILE)
    assemble_spec = dict(preview_spec)
    if settings.get('animatic_ken_burns', True):
        assemble_spec['shot_motions'] = [
            animatic_sketch_backends.infer_motion(board.get(row['id'], {}))
            for row in timeline['shots']
        ]

    def publish(artifacts):
        if not validate_bundle(artifacts):
            raise ValueError('Animatic 清单与媒体不一致，本次不发布')
        return publish_animatic_bundle(root, artifacts,
                                       validate=lambda items: all(raw for _, raw in items))

    def batches(groups, worker):
        results = stage_parallel.parallel_map('animatic', groups, worker)
        for _group, _result, error in results:
            if error:
                raise error
        return [result for _group, result, _error in results]

    build_bundle(project_context(root), path, (), audio, settings,
                 publish=publish, write_temporary=save_bytes, run_batches=batches,
                 render=_timeline_render(settings), workspace=workspace,
                 spec=assemble_spec)
    updated = _compose_timeline_rows(root, timeline, shot_versions, existing_images,
                                   shot_references, clip_map,
                                   dialogue_durations=dialogue_durations)
    _publish_animatic_timeline(root, updated)
    return folder / settings['video_relpath']


def lock_animatic(project, *, rhythm, duration, dialogue_sync):
    """REQ-S04-90/91：三项确认＋时长回写原子事务；任一步失败全回滚。

    写盘顺序（DES-S04-24）：同目录 ``历史版本/`` 时间戳存档 → 原文件原子替换 →
    ``storyboard_selection.adopt`` → 清单（新 ``source_sha256`` ＋三项 True）原子发布。
    """
    from copy import deepcopy
    from datetime import datetime
    from domain import animatic_timeline as timeline_model
    from domain.animatic_service import CONFIRMATIONS, MANIFEST, digest, evidence
    if not all(value is True for value in (rhythm, duration, dialogue_sync)):
        raise ValueError('节奏、时长与对白同步必须全部确认')
    root = Path(project).resolve()
    folder = write_dir(root, 'animatic')
    manifest_path = folder / MANIFEST
    try:
        manifest = file_cache.read_json(manifest_path)
        timeline = file_cache.read_json(folder / timeline_model.TIMELINE_FILE)
    except (OSError, ValueError):
        raise ValueError('尚无 Animatic 成果可锁定') from None
    ok, reason = evidence(root, require_confirmation=False)
    if not ok:
        raise ValueError(reason)
    revisions = timeline_model.needs_revision_ids(timeline)
    if revisions:
        preview = '、'.join(revisions[:6]) + (' 等' if len(revisions) > 6 else '')
        raise ValueError('还有 %d 个镜头标记为「需修改」（%s），请处理后再锁定'
                         % (len(revisions), preview))
    current = {row['id']: row.get('seconds') for row in timeline.get('shots', [])
               if isinstance(row, dict)}
    composed = {row.get('id'): row.get('seconds') for row in manifest.get('shots', [])
                if isinstance(row, dict)}
    if not current or current != composed:
        raise ValueError('时间线改过，请先重新合成')
    source = (root / manifest['source']).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError('分镜源文件不在项目内')
    storyboard, raw_source, _signature = file_cache.read_stable_json_snapshot(source)
    board_seconds = {str(row.get('id')): row.get('duration')
                     for row in storyboard.get('shots', []) if isinstance(row, dict)}
    new_board, changed = timeline_model.writeback_plan(storyboard, timeline)
    if board_seconds == current or not changed:
        return confirm_animatic(root, rhythm=rhythm, duration=duration,
                                dialogue_sync=dialogue_sync)
    from contract.episode_contract import validate_episode
    from contract.storyboard_paths import media_root
    validate_episode(new_board, media_root(source))
    from agent.core import save, save_bytes
    from agent.publication import transaction
    with transaction():
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive = source.parent / '历史版本' / (
            '%s_%s_%s.json' % (source.stem, stamp, digest(raw_source)[:6]))
        save_bytes(archive, raw_source)
        save(source, new_board)
        from orchestrator.storyboard_selection import adopt
        adopt(root, [source])
        data = deepcopy(manifest)
        data['source_sha256'] = file_cache.file_digest(source)
        data['confirmed'] = dict.fromkeys(CONFIRMATIONS, True)
        import contract.artifact_schema as artifact_schema
        data = artifact_schema.stamp('animatic_manifest', data)
        publish_stage_text(manifest_path, json.dumps(data, ensure_ascii=False, indent=2),
                           lambda text: '"rhythm":true' in text.replace(' ', ''),
                           file_cache.published)
    return manifest_path
