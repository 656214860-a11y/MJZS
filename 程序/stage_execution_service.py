"""阶段执行所需的编排器与上下文，不依赖配置面板。"""
import app_logging
import json
from pathlib import Path

import file_cache
import model_pool
import model_router
import skill_budget
import stage_config
import stage_models
from project_context_factory import project_context
from stage_path_service import write_dir


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


def program_of(desktop):
    return getattr(desktop, 'app', None) or None


def keyframe_image_prompt(project, source, shot_id=None, outputs=None, shot_ids=None):
    """L3 为首帧批次任务书注入唯一的项目上下文。"""
    from keyframe_batch import image_prompt
    return image_prompt(source, project_context(project), shot_id, outputs, shot_ids=shot_ids)


def import_delivery_master(project, source, *, settings_snapshot=None, cache=None):
    """交付成片导入编排：L3 负责上下文和发布器注入。"""
    from delivery_import_service import import_final_master
    return import_final_master(
        project_context(project, settings_snapshot=settings_snapshot, cache=cache), source,
        publish=media_import_publisher(project, 'video'))


def local_video_settings_gateway():
    """L3 为本地视频设置服务注入唯一的发布与回滚能力。"""
    import shutil
    from agent.core import save, save_bytes
    return {'publish_json': save, 'publish_bytes': save_bytes,
            'copy_file': shutil.copy2,
            'replace_file': lambda source, target: Path(source).replace(target),
            'published': file_cache.published}


def publish_local_video_settings(project, current_config, options):
    """L3 编排本地视频工作流与项目设置的成对发布。"""
    from local_video_settings_service import save_local_video_settings
    return save_local_video_settings(project_context(project), current_config, options,
                                     gateway=local_video_settings_gateway())


def pet_performance_gateway():
    """L3 为宠物优化账本装配唯一的 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def start_pet_performance_check(program, project, kind='startup'):
    """L3 编排宠物离线基准启动；L4 不直接调用 L2 服务。"""
    from pet_performance_service import start_long_list_check, start_startup_check
    starter = start_long_list_check if kind == 'long_list' else start_startup_check
    return starter(program, project)


def poll_pet_performance_check(session, at=None):
    """L3 轮询宠物离线基准，并向 L2 注入正式账本发布器。"""
    from pet_performance_service import poll_startup_check
    return poll_startup_check(session, project_context(session['project']), at=at,
                              publish=pet_performance_gateway()['publish_json'])


def pet_test_gateway():
    """L3 为宠物增量自检账本装配唯一的 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def start_pet_test_check(program, text=''):
    """L3 编排宠物增量自检启动；L4 不直接调用 L2 服务。"""
    from pet_test_service import start_incremental
    return start_incremental(program, text)


def poll_pet_test_check(session, project, at=None):
    """L3 轮询宠物增量自检，并向 L2 注入正式账本发布器。"""
    from pet_test_service import poll_incremental
    return poll_incremental(session, project_context(project), at=at,
                            publish=pet_test_gateway()['publish_json'])


def import_stage_audio(project, source):
    """音频导入编排：L3 注入校验与有界文件发布器。"""
    from audio_import_service import import_audio
    return import_audio(project, source, publish=media_import_publisher(project, 'audio'))


def media_import_publisher(project, kind):
    from stage_completion_service import publish_imported_media
    from agent.core import read
    from agent.media import validate_import
    from platform_tools import tool_path
    def publish(target, source):
        config_path = Path(project) / 'config.json'
        config = dict(read(config_path)) if config_path.is_file() else {}
        for name in ('ffmpeg', 'ffprobe'):
            config[name] = config.get(name) or tool_path(name)
        return publish_imported_media(target, source, lambda temporary: validate_import(temporary, config, kind), kind)
    return publish


def export_stage_srt(project, episode):
    """字幕导出编排：L3 注入统一文本阶段发布器。"""
    from subtitle_export_service import export_srt
    return export_srt(project, episode, publish=publish_stage_text)


def video_prompt_gateway():
    """L3 为视频提示词草稿与可见成果装配事务发布能力。"""
    from agent.core import restore_bytes, save, save_bytes
    return {'publish_bundle': publish_stage_bundle,
            'read_bytes': lambda path: Path(path).read_bytes(),
            'publish_json': save, 'publish_bytes': save_bytes,
            'restore_bytes': restore_bytes,
            'remove_dir': lambda folder: Path(folder).rmdir()}


def publish_video_prompt(studio, sid, text):
    from video_prompt_publication import publish
    result = publish(studio, sid, text, publish_bundle=video_prompt_gateway()['publish_bundle'])
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def import_video_prompt(studio, sid, text):
    from video_prompt_publication import stage_import
    result = stage_import(studio, sid, text, gateway=video_prompt_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def export_stage_dialogue_script(project, episode, assets):
    """对白脚本导出编排：L3 注入统一文本阶段发布器。"""
    from subtitle_export_service import export_dialogue_script
    return export_dialogue_script(project, episode, assets, publish=publish_stage_text)


def adopt_natural_script(project, source_path):
    """为显式采用的自然剧本版本注入统一发布器。"""
    from script_workspace_service import adopt_natural_script as adopt
    return adopt(project, source_path, publish=publish_stage_text)


def restart_writing_preparation(project, stage):
    """显式重写入口复用阶段发布器，不由桌面直接写确认台账。"""
    from writing_api import restart_preparation
    return restart_preparation(project, stage, publish=publish_stage_text)
def confirm_writing_preparation(project, stage, path):
    """显式把当前文件登记为该阶段确认输出的编排入口，复用统一阶段发布器。"""
    from writing_api import confirm_preparation_document
    return confirm_preparation_document(project, stage, path, publish=publish_stage_text)




def reply_to_writing(project, creative, cancelled=None, *, user_message=None, request_model=None):
    """剧本模型调用编排：为所有可见剧本成果注入统一发布器。"""
    from writing_api import reply
    try:
        return reply(project, creative, cancelled=cancelled,
                     publish=publish_stage_text, archive=publish_response_archive, user_message=user_message, request_model=request_model)
    except (ValueError, OSError, RuntimeError) as exc:
        from writing_api import WritingCancelledError
        response = getattr(exc, 'rejected_response', None)
        if isinstance(exc, WritingCancelledError) or response is None:
            raise
        return response


def collect_writing_quality(project, script_path):
    """Recover a desktop delivery through the same report publisher as API/CLI."""
    from writing_quality import split_response, publish_reports
    from stage_path_service import write_dir
    from script_contract import require_natural_script
    target = Path(script_path)
    folder = write_dir(project, 'script').resolve()
    if not target.resolve().is_relative_to(folder):
        raise ValueError('质检仅回收当前剧本准备目录内的文件')
    before = target.stat()
    response = target.read_text(encoding='utf-8')
    body, _, error = split_response(response)
    body = require_natural_script(body)
    result = publish_reports(response, target, folder / 'quality', publish=publish_stage_text).data
    after = target.stat()
    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise ValueError('回收期间正文变化，请等待本轮写入完成')
    if not error and response.strip() != body.strip():
        publish_stage_text(target, body.strip() + '\n', lambda value: bool(require_natural_script(value)), lambda _target: None)
    return dict(result, text=body, natural_script_path=str(target))


def desktop_settings_gateway():
    """L3 为桌面级偏好设置注入唯一 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def publish_desktop_preferences(settings_path, current, updates):
    """桌面设置持久化只经 L3 装配的发布器。"""
    from desktop_settings_service import publish_desktop_settings
    return publish_desktop_settings(settings_path, current, updates,
                                    publish=desktop_settings_gateway()['publish_json'])


def legacy_adoption_gateway():
    """L3 为旧目录归位记录装配目录与 JSON 发布能力。"""
    from agent.core import save
    return {'publish_json': save,
            'make_dir': lambda folder: Path(folder).mkdir(parents=True, exist_ok=True)}


def record_stage_legacy_adoption(project, linked_paths, now=None):
    """旧目录归位记录只经 L3 网关发布。"""
    from legacy_adoption_service import record_legacy_adoption
    result = record_legacy_adoption(project, linked_paths, now=now,
                                    gateway=legacy_adoption_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def idea_attachment_local_mode(project):
    """显式 API 选择优先；其余按 writing 实际目标识别本地 Agent。"""
    import model_pool
    from workflow_engines import current_config
    import writing_api
    if writing_api.model_label(project):
        return False
    config = current_config(project, 'writing')
    engine = model_pool.desktop_engine(config.get('model')) or config.get('engine')
    return engine in {'codex', 'claude', 'qwen'} and not config.get('api')


def archive_idea_attachments(project, paths, now=None):
    """剧本准备附档归档编排：L3 注入统一文本阶段发布器。"""
    from idea_attachments import store

    def publish_attachment(target, text):
        if isinstance(text, bytes):
            from agent.core import save_bytes
            save_bytes(target, text)
            return target
        return publish_stage_text(
            target, text, lambda value: bool(value.strip()), lambda _target: None)

    result = store(project_context(project), paths, now=now, publish=publish_attachment,
                   local_mode=idea_attachment_local_mode(project))
    if not result.ok:
        raise ValueError(result.reason)
    sync_writing_attachment_locks(project)
    return result.data


def stage_idea_attachment_paths(project, limit=None):
    """列出已入库创意附档；项目根只由 L3 上下文提供。"""
    from idea_attachments import uploaded
    return uploaded(project_context(project), limit, local_mode=idea_attachment_local_mode(project))


def stage_idea_attachment_reference(project, message='', selected_paths=()):
    """为剧本准备对话解析已入库附档，不向 L2 暴露裸项目路径。"""
    from idea_attachments import referenced, brief_sources
    from workflow_engines import current_config
    context = project_context(project)
    local_mode = idea_attachment_local_mode(project)
    result = referenced(context, message, selected_paths,
                        local_mode=local_mode, markdown_only=local_mode and
                        current_config(project, 'writing').get('engine') == 'claude')
    result.update(brief_sources(context, result))
    return result


def prepare_idea_attachment_selection(project, paths):
    """仅预检刚上传的附件，不把历史最近三份混入上传结果。"""
    from idea_attachments import prepare
    return prepare(paths, local_mode=idea_attachment_local_mode(project), context=project_context(project))


def stage_idea_brief_defaults(project, *, reference=None):
    """复用本轮引用的解析副本，不再扫描目录或改变模型投递上下文。"""
    from idea_brief_form import extract_brief_creation
    if reference is None:
        reference = stage_idea_attachment_reference(project)
    values = {}
    for text in reference.get('brief_texts', ()):
        fields = extract_brief_creation(text)
        for label, value in fields.items():
            values.setdefault(label, value)
    return {'values': values, 'skipped': reference.get('brief_unreadable', ())}


def prepare_idea_semantic_brief(project, draft, reference):
    from idea_semantic_brief_service import semantic_brief_request
    return semantic_brief_request(project_context(project), draft, reference,
                                  local_mode=idea_attachment_local_mode(project))


def validate_idea_semantic_sources(request):
    for source, modified, size in request['fingerprints']:
        stat = source.stat()
        if (stat.st_mtime_ns, stat.st_size) != (modified, size):
            raise ValueError('附档内容已变化，未套用旧提取结果，请重新发送。')


def read_idea_semantic_brief(request):
    """只轮询本次唯一文件；模型尚未原子发布时继续等待。"""
    from idea_semantic_brief_service import SEMANTIC_BRIEF_MAX_BYTES, semantic_brief_values
    path = request['path']
    if not path.is_file():
        return None
    if path.is_symlink() or path.resolve().parent != path.parent.resolve() or path.stat().st_size > SEMANTIC_BRIEF_MAX_BYTES:
        raise ValueError('简报提取结果路径或大小无效。')
    validate_idea_semantic_sources(request)
    try:
        data = file_cache.read_json(path)
    except ValueError as exc:
        raise ValueError('简报提取结果不是有效 JSON，请让 Agent 完成后重新发送。') from exc
    return semantic_brief_values(data, request['request_id'], request['source'])


def idea_chat_gateway():
    """为 ``idea_chat`` 注入缓存读取与原子发布；L2 不可自行落盘。"""
    from agent.core import save, save_text
    from storage_maintenance import recycle_paths
    return {
        'read_json': file_cache.read_json,
        'publish_json': save,
        'publish_text': save_text,
        'recycle_paths': recycle_paths,
    }


def asset_batch_gateway():
    """L3 为资产批处理服务装配唯一的正式读写入口。"""
    import shutil
    from agent.core import file_hash, save, save_bytes
    return {'read_json': file_cache.read_json, 'publish_json': save,
            'publish_bytes': save_bytes, 'file_hash': file_hash,
            'copy_file': shutil.copy2,
             'replace_file': lambda source, target: Path(source).replace(target)}


def asset_plan_gateway():
    """L3 为资产计划与续跑台账装配唯一的正式发布能力。"""
    from agent.core import save, save_bytes, save_text
    from file_cache import remove_temporary_file
    return {'publish_json': save, 'publish_bytes': save_bytes,
            'publish_text': save_text, 'remove_file': remove_temporary_file}


def sync_asset_plan(project, episode_dir, storyboard=None, *, scope='current', _adopting=False):
    """L3 同步资产计划，避免 L2 自行选择发布器。"""
    from asset_plan import sync_plan
    episode_dir = prepare_asset_write(project, episode_dir)
    return unwrap_service_result(sync_plan(project, episode_dir, storyboard, scope=scope, _adopting=_adopting,
                                            gateway=asset_plan_gateway(), context=project_context(project)))


def update_asset_plan_fields(project, episode_dir, aid, values):
    from asset_plan import update_fields
    episode_dir = prepare_asset_write(project, episode_dir)
    return unwrap_service_result(update_fields(project, episode_dir, aid, values, gateway=asset_plan_gateway()))


def apply_asset_plan_gate_choice(project, key, choice, episode_dir=''):
    from asset_plan import apply_gate_choice
    episode_dir = prepare_asset_write(project, episode_dir)
    return unwrap_service_result(apply_gate_choice(project, key, choice, episode_dir, gateway=asset_plan_gateway()))


def plan_unattended_assets(project, base, sources, scope='adopted'):
    """L3 为无人值守资产计划装配唯一的发布网关。"""
    from asset_batch_service import unattended_plan
    base = prepare_asset_write(project, base)
    return unattended_plan(project, base, sources, scope, gateway=asset_plan_gateway(),
                           context=project_context(project))


def note_asset_resume_round(project, ids, limit=None, now=None):
    from asset_resume import note_round
    result = note_round(project, ids, limit=limit, now=now,
                        publish=asset_plan_gateway()['publish_json'])
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def adopt_asset_storyboards(project, values):
    from storyboard_selection import adopt
    return adopt(project, values, gateway=asset_plan_gateway())


def remove_asset_storyboards(project, values):
    from storyboard_selection import remove
    return remove(project, values, gateway=asset_plan_gateway())


def poll_asset_storyboard_adoption(project, minimum_age=10):
    from storyboard_selection import adopt_pending
    return adopt_pending(project, minimum_age=minimum_age, gateway=asset_plan_gateway())


def release_uncertain_asset_batch(project, ids):
    """L3 为确认后的资产批次未知提交记录提供唯一放开入口。"""
    from asset_batch_state_service import release_uncertain
    return release_uncertain(None, ids, context=project_context(project),
                             publish=asset_batch_gateway()['publish_json'])


def asset_batch_settings_gateway():
    """L3 为资产批量设置服务注入唯一的项目设置发布器。"""
    from agent.core import save
    return {'publish_json': save}


def save_asset_batch_settings(project, options, categories=None, restored_model_id=None):
    from asset_batch_settings_service import save_settings
    return save_settings(project, options, categories, restored_model_id,
                         publish=asset_batch_settings_gateway()['publish_json'])


def remove_asset_batch_model(project, url, model, model_id):
    from asset_batch_settings_service import remove_model
    return remove_model(project, url, model, model_id,
                        publish=asset_batch_settings_gateway()['publish_json'])


def asset_detail_gateway():
    """L3 为资产详情图片绑定注入唯一的回滚发布器。"""
    return asset_plan_gateway()


def bind_asset_canonical_view(project, episode_dir, aid, view, source):
    """L3 编排资产详情正典板绑定。"""
    from asset_detail_service import bind_canonical_view
    episode_dir = prepare_asset_write(project, episode_dir)
    result = bind_canonical_view(project, episode_dir, aid, view, source,
                                gateway=asset_detail_gateway(), context=project_context(project))
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def bind_asset_variant_thumbnail(project, episode_dir, aid, state_id, source):
    """L3 编排资产详情状态变体缩略图绑定。"""
    from asset_detail_service import bind_variant_thumbnail
    episode_dir = prepare_asset_write(project, episode_dir)
    result = bind_variant_thumbnail(project, episode_dir, aid, state_id, source,
                                   gateway=asset_detail_gateway(), context=project_context(project))
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def pending_generated_assets(project, base):
    """L3 统一装配自动导入生成资产时的项目上下文。"""
    from asset_generated_import_service import pending_generated
    return pending_generated(project, base, context=project_context(project))


def import_pending_generated_assets(project, base, report=None):
    """L3 装配生成资产导入所需的上下文与发布网关。"""
    from asset_generated_import_service import import_pending_generated
    base = prepare_asset_write(project, base)
    return import_pending_generated(project, base, report, gateway=asset_batch_gateway(),
                                    context=project_context(project))


def tts_gateway():
    """L3 为 TTS 服务装配唯一的正式发布器；L2 不可自行写设置或阶段成果。"""
    from agent.core import save, save_bytes
    return {'publish_json': save, 'publish_bytes': save_bytes}


def save_tts_key(base_url, model, voice, key, voices=None, speeds=None):
    from tts_api import save_key
    return save_key(base_url, model, voice, key, voices, speeds, gateway=tts_gateway())


def publish_tts_full_track(project, signature, raw):
    from tts_api import publish_full_track
    return publish_full_track(project_context(project), signature, raw, gateway=tts_gateway())


def reusable_tts_full_track(project, signature):
    """L3 为整段配音复用检查注入项目上下文。"""
    from tts_api import reusable_full_track
    return reusable_full_track(project_context(project), signature)


def storyboard_working_source(project, source):
    """L3 为分镜生命周期的工作稿判定注入项目上下文。"""
    from storyboard_lifecycle import is_working_source
    return is_working_source(project_context(project), source)


def retire_storyboard(project, source, target, expected, publish):
    """L3 为已发布定稿退役工作分镜注入项目上下文。"""
    from storyboard_lifecycle import retire
    return retire(project_context(project), source, target, expected, publish=publish)


def refresh_storyboard_studios(desktop, project):
    """L3 为定稿后的已开分镜工作集刷新注入项目上下文。"""
    from storyboard_lifecycle import refresh_open_studios
    return refresh_open_studios(desktop, project_context(project))


def white_model_shot_directory(project, sid, workspace_path=None, source=None):
    """L3 为白模镜头工作目录解析注入项目上下文；source 明确本次是哪一集。"""
    from white_model_service import shot_directory
    return shot_directory(project_context(project), sid, workspace_path, source)


def migrate_white_model_directories(project):
    """L3 为白模旧目录迁移注入项目上下文与正式发布器。"""
    from agent.core import save
    from white_model_service import migrate_legacy_directories
    return migrate_legacy_directories(project_context(project), publish=save)


def run_tts_lines(lines, folder, generate=None, report=None, stop=None, episode=None, project=None):
    from tts_api import run_lines
    return run_lines(lines, folder, generate, report, stop, gateway=tts_gateway(), episode=episode, project=project)


def cloud_video_gateway():
    """L3 为云视频配置服务装配唯一的正式 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def cloud_video_session_folder(project, kind, base, model, source):
    """L3 统一注入项目上下文并创建/复用云视频会话目录。"""
    from cloud_video_service import session_folder
    result = session_folder(project_context(project), kind, base, model, source)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def cloud_video_saved_provider_key(project, kind, providers, remembered=None, base_url=None, module_file=None):
    """L3 统一注入项目上下文，供 L4 查询旧会话兼容凭据。"""
    from cloud_video_service import saved_provider_key
    return saved_provider_key(project_context(project), kind, providers, remembered, base_url, module_file)


def publish_cloud_video_session_config(config_path, config, prefs_path, prefs):
    from cloud_video_service import publish_session_config
    result = publish_session_config(config_path, config, prefs_path, prefs, gateway=cloud_video_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def publish_cloud_video_workspace_preference(prefs_path, prefs):
    from cloud_video_service import publish_workspace_preference
    result = publish_workspace_preference(prefs_path, prefs, gateway=cloud_video_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def publish_cloud_video_studio_config(config_path, config):
    from cloud_video_service import publish_studio_config
    result = publish_studio_config(config_path, config, gateway=cloud_video_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def video_lifecycle_gateway():
    """L3 向视频生命周期服务注入唯一 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def confirm_gates_gateway():
    """L3 为确认门禁注入唯一的正式 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def record_stage_confirmation(project, key, choice='', by='human', state='applied', digest=''):
    """记录确认门禁；L4 不得自行装配或直写确认账本。state 见 confirm_gates.record。"""
    from confirm_gates import record
    return record(project, key, choice, by=by, state=state, digest=digest,
                  publish=confirm_gates_gateway()['publish_json'],
                  context=project_context(project))


def forget_stage_confirmation(project, key):
    """撤销确认门禁；保持与记录入口相同的 L3 发布边界。"""
    from confirm_gates import forget
    return forget(project, key, publish=confirm_gates_gateway()['publish_json'],
                  context=project_context(project))


def adopt_asset_plan_choice(project, key, choice, digest=''):
    """准备→落盘→确认走完一条路：只有落盘成功才把确认记成 applied。

    先记 pending：进程中断只留下 pending，候选会重新摆出、可再点一次；落盘失败记 failed，
    同样不算确认完成。任何一步没走完，都不会出现「未采用却已审核通过」（O10）。
    """
    from confirm_gates import APPLIED, FAILED, PENDING
    record_stage_confirmation(project, key, choice, state=PENDING, digest=digest)
    try:
        result = apply_asset_plan_gate_choice(project, key, choice)
    except Exception:
        try:
            record_stage_confirmation(project, key, choice, state=FAILED, digest=digest)
        except Exception:
            app_logging.swallowed()
        raise
    record_stage_confirmation(project, key, choice, state=APPLIED, digest=digest)
    return result


def reopen_asset_plan_choices(project, aid):
    """按正典板、锚点顺序撤销；失败即停止，保留既有部分完成语义。"""
    dropped = []
    for key in ('canon:' + aid, 'anchor:' + aid):
        forget_stage_confirmation(project, key)
        dropped.append(key)
    return dropped


def run_stage_confirmation_gate(project, gate_id, *, shots=None, assets=None, ledger=None):
    """L3 运行确认门禁，并为需要确认记忆的 L2 注入项目上下文。"""
    from confirm_gates import run
    return run(gate_id, project=project, shots=shots, assets=assets, ledger=ledger,
               context=project_context(project))


def previs_routing_gateway():
    """L3 为白模分流策略注入唯一的正式 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def save_stage_previs_override(project, source, shot_id, value):
    """保存白模复杂度人工覆写；L4 只委托 L3。"""
    from previs_routing import set_override
    return set_override(project_context(project), source, shot_id, value,
                        publish=previs_routing_gateway()['publish_json'])


def dispatch_stage_previs(project, source, shot_ids, state, monitor=False, start_complex=None):
    """发布白模分流记录；执行器仍由调用方注入，路由落盘只经 L3。"""
    from previs_routing import dispatch
    return dispatch(project_context(project), source, shot_ids, state, monitor=monitor,
                    start_complex=start_complex,
                    publish=previs_routing_gateway()['publish_json'])


def previs_entries(project, source):
    from previs_routing import entries
    return entries(project_context(project), source)


def previs_ready(project, shot_id, source=None):
    from previs_routing import ready
    return ready(project_context(project), shot_id, source)


def record_previs_evidence(project, sid, source, media=None):
    """L3 为白模就绪登记注入项目上下文与正式发布器。"""
    from agent.core import save
    from white_model_service import record_evidence
    root = white_model_shot_directory(project, sid, source=source)
    return record_evidence(root, sid, source, publish=save, media=media)


def previs_records_directory(project, state):
    from previs_routing import records_directory
    return records_directory(project_context(project), state)


def previs_automatic_candidates(project, source, shots, wait_for_frames=False, pending_frame_ids=None):
    from previs_routing import automatic_candidates
    return automatic_candidates(project_context(project), source, shots, wait_for_frames, pending_frame_ids)


def previs_automatic_engine(project, read_settings, engines):
    from previs_routing import automatic_engine
    return automatic_engine(project_context(project), read_settings, engines)


def storyboard_catalog(project, kind, ignored=None):
    from storyboard_catalog_service import catalog
    return catalog(project_context(project), kind) if ignored is None else catalog(project_context(project), kind, ignored)


def storyboard_produced_scripts(project, entries=None):
    from storyboard_catalog_service import produced_scripts
    return produced_scripts(project_context(project), entries)


def storyboard_produced_episodes(project, entries=None):
    from storyboard_catalog_service import produced_episodes
    return produced_episodes(project_context(project), entries)


def storyboard_default_source(project):
    from storyboard_catalog_service import default_source
    return default_source(project_context(project))


def storyboard_resolve_source(project, path):
    from storyboard_catalog_service import resolve_source
    return resolve_source(project_context(project), path)


def storyboard_board_source_script(project, board):
    from storyboard_catalog_service import board_source_script
    return board_source_script(project_context(project), board)


def storyboard_working_dir(project):
    from storyboard_catalog_service import working_dir
    return working_dir(project_context(project))


def storyboard_document_dir(project):
    from storyboard_catalog_service import document_dir
    return document_dir(project_context(project))


def storyboard_file_snapshot(project, ignored=None):
    from storyboard_catalog_service import file_snapshot
    return file_snapshot(project_context(project)) if ignored is None else file_snapshot(project_context(project), ignored)


def previs_progress_gateway():
    """L3 为 Blender 白模进度注入唯一的原子文本发布器。"""
    from agent.core import save_text
    return {'publish_text': save_text}


def publish_stage_previs_progress(path, shot_id, stage, completed=None, total=None):
    """发布单镜头白模进度；宿主兼容门面只委托此 L3 入口。"""
    from previs_progress_service import publish
    return publish(path, shot_id, stage, completed, total,
                   publish_text=previs_progress_gateway()['publish_text'])


def install_stage_previs_progress(path, shot_id):
    """为 Blender 安装进度回调，并向 L2 注入正式发布器。"""
    from previs_progress_service import install_blender_progress
    return install_blender_progress(path, shot_id,
                                    publish_text=previs_progress_gateway()['publish_text'])


def storyboard_edit_gateway():
    """L3 为定稿分镜编辑服务注入唯一的 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def save_edited_stage_storyboard(path, data):
    """保存已校验的定稿分镜；L3 保持正式发布器唯一装配点。"""
    from storyboard_edit_service import save_edited_json
    return save_edited_json(prepare_legacy_stage_path(path), data,
                            publish=storyboard_edit_gateway()['publish_json'])


def storyboard_gateway():
    from agent.core import save, save_bytes
    from file_cache import remove_temporary_file
    from agent.core import save_bytes_new
    from storage_maintenance import recycle_paths
    return {'publish_json': save, 'publish_bytes': save_bytes, 'publish_bytes_new': save_bytes_new,
            'recycle_paths': recycle_paths,
            'remove_temporary_file': remove_temporary_file}


def publish_final_storyboard_bundle(episodefile, assetfile, episode, assets, validate):
    from storyboard_storage import publish_final_bundle
    return unwrap_service_result(publish_final_bundle(episodefile, assetfile, episode, assets, validate,
                                                       gateway=storyboard_gateway()))


def normalize_storyboard_for_desktop(desktop):
    from storyboard_storage import normalize_for_desktop
    return unwrap_service_result(normalize_for_desktop(desktop, gateway=storyboard_gateway()))


def mark_stage_video_deleted(source, sid, versions):
    from video_lifecycle_service import mark_video_deleted
    result = mark_video_deleted(prepare_legacy_stage_path(source), sid, versions, gateway=video_lifecycle_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_stage_video_options(source, sid, selected, generate_audio, is_local):
    from video_lifecycle_service import save_video_options
    result = save_video_options(prepare_legacy_stage_path(source), sid, selected, generate_audio, is_local,
                              gateway=video_lifecycle_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_stage_white_model_upload(source, sid, enabled):
    from video_lifecycle_service import save_white_model_upload
    result = save_white_model_upload(prepare_legacy_stage_path(source), sid, enabled, gateway=video_lifecycle_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_stage_editing_checklist(project, text):
    """剪辑清单保存编排：保留用户清空清单的既有语义。"""
    from edit_service import save_editing_checklist

    def publish_checklist(target, value):
        return publish_stage_text(
            target, value, lambda _value: True, lambda _target: None, allow_empty=True)

    result = save_editing_checklist(project, text, publish=publish_checklist,
                                    context=project_context(project))
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def publish_handoff_bundle(project, name, artifacts, *, auto=False, summary=None):
    """交接包发布编排：L3 负责目录切换、字节发布、可校验清单登记与旧自动包回收。"""
    root = Path(project).resolve()
    edit_dir = write_dir(root, 'edit')
    final = edit_dir / str(name)
    if final.parent != edit_dir:
        raise ValueError('交接包目标越界。')
    if auto and final.exists() and not (final / '交接包标记.json').is_file():
        raise ValueError('已有同名目录且不是自动生成的交接包，请先改名或移走：' + str(final))
    staging = edit_dir / '自动交接包.生成中'
    output = staging if auto else final
    if auto and staging.exists():
        from storage_maintenance import recycle_paths
        recycle_paths(root, [staging], '清理未完成自动交接包')
    payload = {}
    for item in artifacts:
        filename = str(item['name'])
        target = output / filename
        if target.parent != output:
            raise ValueError('交接包文件名越界。')
        data = item.get('data')
        if data is None:
            data = Path(item['source']).read_bytes()
        payload[target] = bytes(data)
    from handoff_service import BUNDLE_MANIFEST_NAME, build_bundle_manifest
    manifest = build_bundle_manifest(summary, [{'name': Path(target).name, 'data': data}
                                               for target, data in payload.items()])
    payload[output / BUNDLE_MANIFEST_NAME] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    publish_stage_bundle(payload, lambda _items: True, lambda: None)
    if auto:
        if final.exists():
            from storage_maintenance import recycle_paths
            if not recycle_paths(root, [final], '更新自动交接包'):
                raise ValueError('旧自动交接包未能移入回收站，已保留原包')
        staging.replace(final)
    return final


def publish_writing_preparation(project, name, artifacts):
    """剧本准备工作区发布编排：L3 定位阶段目录并原子发布完整成果包。"""
    root = Path(project).resolve()
    script_dir = write_dir(root, 'script')
    output = script_dir / str(name)
    if output.parent != script_dir:
        raise ValueError('剧本准备工作区目标越界。')
    payload = {}
    for item in artifacts:
        target = output / str(item['name'])
        if not target.is_relative_to(output):
            raise ValueError('剧本准备工作区文件名越界。')
        data = item.get('data')
        if data is None:
            data = Path(item['source']).read_bytes()
        payload[target] = bytes(data)
    publish_stage_bundle(payload, lambda _items: True, lambda: None)
    return output


def publish_idea_creative(project, artifacts):
    """创意文件发布编排：L3 定位剧本阶段并原子发布分类成果。"""
    root = Path(project).resolve()
    script_dir = write_dir(root, 'script')
    payload = {}
    published = {}
    directories = set()
    for item in artifacts:
        name = str(item['name']).replace('\\', '/')
        target = script_dir.joinpath(*name.split('/'))
        try:
            target.resolve().relative_to(script_dir.resolve())
        except (OSError, ValueError) as exc:
            raise ValueError('创意文件目标越界。') from exc
        data = item.get('data')
        if data is None:
            data = Path(item['source']).read_bytes()
        payload[target] = bytes(data)
        published[name] = target
        for directory in item.get('directories', ()):
            folder = script_dir.joinpath(*str(directory).replace('\\', '/').split('/'))
            try:
                folder.resolve().relative_to(script_dir.resolve())
            except (OSError, ValueError) as exc:
                raise ValueError('创意分类目录越界。') from exc
            directories.add(folder)
    publish_stage_bundle(payload, lambda _items: True, lambda: None)
    for folder in directories:
        folder.mkdir(parents=True, exist_ok=True)
    return published


def publish_keyframe_episode(target, episode):
    """由 L3 原子发布首帧索引 JSON，供首帧生命周期服务注入。"""
    return publish_stage_text(
        target, json.dumps(episode, ensure_ascii=False, indent=2),
        lambda value: isinstance(json.loads(value), dict), lambda _target: None)


def delete_stage_keyframe(base, source, episode, shot):
    """首帧删除编排：L3 注入索引发布器。"""
    from keyframe_lifecycle_service import delete_keyframe
    return delete_keyframe(prepare_legacy_stage_path(base), prepare_legacy_stage_path(source), episode, shot, publish=publish_keyframe_episode)


def restore_stage_keyframe(base, source, episode, shot):
    """首帧恢复编排：L3 注入索引发布器。"""
    from keyframe_lifecycle_service import restore_keyframe
    return restore_keyframe(prepare_legacy_stage_path(base), prepare_legacy_stage_path(source), episode, shot, publish=publish_keyframe_episode)


def replace_stage_keyframe(base, source, episode, shot, data):
    """首帧替换编排：L3 注入图片与索引两个原子发布器。"""
    from keyframe_lifecycle_service import replace_keyframe
    return replace_keyframe(
        prepare_legacy_stage_path(base), prepare_legacy_stage_path(source), episode, shot, data, publish=publish_stage_bytes,
        publish_episode=publish_keyframe_episode)


def save_automatic_assemble_marker(project, digest, master, completed_at):
    """自动粗剪完成标记：L3 定位阶段目录并注入原子发布器。"""
    from edit_service import AUTOMATIC_ASSEMBLE_MARKER_NAME, save_automatic_assemble_marker as save_marker
    target = write_dir(Path(project), 'edit') / AUTOMATIC_ASSEMBLE_MARKER_NAME

    def publish_marker(path, payload):
        return publish_stage_text(
            path, json.dumps(payload, ensure_ascii=False, sort_keys=True),
            lambda text: isinstance(json.loads(text), dict), lambda _target: None)

    result = save_marker(target, digest, master, completed_at, publish=publish_marker)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_automatic_handoff_marker(project, digest, folder, shot_count):
    """自动交接完成标记：L3 定位阶段目录并注入原子发布器。"""
    from handoff_service import AUTOMATIC_HANDOFF_MARKER_NAME, save_automatic_handoff_marker as save_marker
    target = write_dir(Path(project), 'edit') / AUTOMATIC_HANDOFF_MARKER_NAME

    def publish_marker(path, payload):
        return publish_stage_text(
            path, json.dumps(payload, ensure_ascii=False, sort_keys=True),
            lambda text: isinstance(json.loads(text), dict), lambda _target: None)

    result = save_marker(target, digest, folder, shot_count, publish=publish_marker)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def publish_stage_handoff_bundle(project, shots, rows, subtitle=None, auto=False):
    """交接包编排：L3 注入项目上下文与唯一阶段发布器。"""
    from handoff_service import publish_bundle
    result = publish_bundle(project, shots, rows, subtitle, auto,
                            publish=publish_handoff_bundle,
                            context=project_context(project))
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def verify_handoff_bundle(folder):
    """离线校验一个已解包的交接包：读清单、按清单核对每个文件，只读不改。"""
    from handoff_service import BUNDLE_MANIFEST_NAME, verify_manifest
    folder = Path(folder).resolve()
    manifest_path = folder / BUNDLE_MANIFEST_NAME
    if not manifest_path.is_file():
        return {'ok': False, 'problems': ['缺少交接包清单，无法离线校验：' + BUNDLE_MANIFEST_NAME],
                'missing': [], 'count': 0, 'label': ''}
    try:
        manifest = file_cache.read_json(manifest_path)
    except (OSError, ValueError):
        manifest = None
    if manifest is None:
        return {'ok': False, 'problems': ['交接包清单读不出来或格式坏了'], 'missing': [], 'count': 0, 'label': ''}

    def probe(name):
        path = (folder / str(name)).resolve()
        if not path.is_relative_to(folder):
            raise OSError('交接包条目越界：' + str(name))
        if not path.is_file():
            raise OSError('交接包文件缺失：' + str(name))
        return path.stat().st_size, file_cache.file_digest(path)
    return verify_manifest(manifest, probe)


def _model_ids(desktop, stage):
    pet = getattr(desktop, 'pet', None)
    getter = getattr(pet, 'agent_model_records', None)
    try:
        records = getter() if callable(getter) else model_pool.pool(program=program_of(desktop))
    except Exception:
        records = {}
    ids = {item[0] for item in model_pool.options(records, with_auto=True)}
    ids.update(value for value, _label in stage_models.production_choices(stage, getattr(desktop, 'root', None)))
    return ids


def build_orchestrator(desktop, project):
    import skill_orchestrator
    errors = getattr(desktop, 'errors', None)
    if not isinstance(errors, list): errors = []
    return skill_orchestrator.default_orchestrator(
        bus=getattr(desktop, 'bus', None), errors=errors, project=project,
        router=model_router.ModelRouter(budget=skill_budget.for_project(project), program=program_of(desktop)))


def stage_context(desktop, stage, function=None, extra=None):
    project = getattr(desktop, 'root', None)
    context = {'project': str(project) if project else '', 'stage': stage, 'function': function}
    if project and stage:
        try: chosen = stage_config.get(project, stage)['model']
        except Exception: chosen = ''
        if chosen and chosen != model_router.AUTO and chosen not in _model_ids(desktop, stage): chosen = ''
        context['projectModel'] = chosen
    if extra: context.update({key: value for key, value in extra.items() if value is not None})
    return context


def recover_stage_publications():
    """在打开项目、读取直接路径之前恢复中断的成果事务。"""
    from agent.publication import recover_pending
    recover_pending()


def publish_stage_text(target, text, validate, update_index, encoding='utf-8', *, allow_empty=False):
    """按“校验 → 原子发布 → 索引更新”发布单份阶段文本成果。

    ``validate`` 和 ``update_index`` 都是调用方所属阶段的既有契约：前者必须在正式
    文件出现前拒绝不合格内容，后者只会在发布成功后执行。默认拒绝空正文；仅明确允许
    用户清空维护清单的 L3 编排入口可传 ``allow_empty=True``，L2 不得自行放宽。索引
    更新失败时恢复本次发布前的成果，并抛出异常；调用方因此不会取得成功返回值，也不得
    据此标记阶段完成。
    """
    if not callable(validate):
        raise TypeError('阶段成果发布需要内容校验器。')
    if not callable(update_index):
        raise TypeError('阶段成果发布需要索引更新器。')
    target = Path(target)
    value = str(text)
    if not value.strip() and not allow_empty:
        raise ValueError('阶段成果正文不能为空，未发布成果。')
    verdict = validate(value)
    if verdict is False:
        raise ValueError('阶段成果内容校验未通过，未发布成果。')

    from agent.core import save_text
    from agent.publication import transaction
    with transaction():
        save_text(target, value, encoding=encoding)
        update_index(target)
    return target


def publish_stage_bytes(target, data, validate, update_index):
    """按文本成果同一编排契约发布二进制阶段成果。"""
    if not callable(validate):
        raise TypeError('阶段成果发布需要内容校验器。')
    if not callable(update_index):
        raise TypeError('阶段成果发布需要索引更新器。')
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError('二进制阶段成果必须是 bytes、bytearray 或 memoryview。')
    target = Path(target)
    value = bytes(data)
    if not value:
        raise ValueError('阶段成果二进制内容不能为空，未发布成果。')
    verdict = validate(value)
    if verdict is False:
        raise ValueError('阶段成果内容校验未通过，未发布成果。')

    from agent.core import save_bytes
    from agent.publication import transaction
    with transaction():
        save_bytes(target, value)
        update_index(target)
    return target


def publish_stage_bundle(artifacts, validate, update_index):
    """原子发布多份关联成果；任一写入或索引失败均恢复整包旧版本。"""
    if not callable(validate):
        raise TypeError('阶段成果发布需要内容校验器。')
    if not callable(update_index):
        raise TypeError('阶段成果发布需要索引更新器。')
    items = tuple((Path(path), bytes(data)) for path, data in artifacts.items())
    if not items:
        raise ValueError('阶段成果包不能为空，未发布成果。')
    if len({path for path, _data in items}) != len(items):
        raise ValueError('阶段成果包包含重复目标，未发布成果。')
    if any(not data for _path, data in items):
        raise ValueError('阶段成果包包含空内容，未发布成果。')
    verdict = validate(items)
    if verdict is False:
        raise ValueError('阶段成果包内容校验未通过，未发布成果。')

    from agent.core import save_bytes
    from agent.publication import transaction
    with transaction():
        for path, data in items:
            save_bytes(path, data)
        update_index()
    return tuple(path for path, _data in items)


def project_registry_gateway():
    """为 ``projects`` 注入唯一的读取、发布及回滚边界。

    项目登记是 L2 业务规则；它不能自行导入底层读写或复制原语。这个小型
    网关由 L3 装配，保留原有缓存读取、原子发布与复制元数据语义。
    """
    from agent.core import restore_bytes, save, save_bytes
    from shutil import copy2, copytree
    return {
        'read_json': file_cache.read_json,
        'read_bytes': lambda path: Path(path).read_bytes(),
        'publish_json': save,
        'publish_bytes': save_bytes,
        'restore_bytes': restore_bytes,
        'copy_file': copy2,
        'copy_tree': copytree,
    }


def import_writing_project(root, json_file):
    """L3 编排剧本 JSON 导入与其校验报告发布。"""
    from writing import import_project
    from workflow_context_controller import workflow_context_gateway
    result = import_project(root, json_file, gateway=project_registry_gateway(),
                            publish_report=workflow_context_gateway()['publish_json'])
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def prepare_writing_project(root, brief, stage, target):
    """L3 编排剧本任务书发布并只向界面交付成功数据。"""
    from writing import prepare
    result = prepare(root, brief, stage, target, publish=publish_writing_preparation)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def unwrap_service_result(result):
    """L3 解包 L2 服务结果；L4 只接收既有业务数据或可展示异常。"""
    # 旧桌面测试桩仍返回裸值；正式写服务总是返回 ServiceResult。
    if not hasattr(result, 'ok'):
        return result
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


unwrap_project_result = unwrap_service_result


def require_formal_asset_generation(project, *, online_model):
    """生成正式资产前核验 SG-B 与线上模型；纯计划和浏览不受影响。"""
    import stage_parallel
    gate = stage_parallel.evaluate(project, 'assets')
    if not gate['ok']:
        raise ValueError(stage_parallel.blocked_text(gate))
    if not online_model:
        raise ValueError('正式资产请选择线上 API 模型；本地草图请在分镜预演阶段生成')


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


import threading

_STAGE_COPY_LOCK = threading.RLock()


def prepare_stage_write(project, stage, *, source=None):
    with _STAGE_COPY_LOCK:
        return _copy_stage_for_write(project, stage, source=source)


def _copy_stage_for_write(project, stage, *, source=None):
    """首次修改前复制历史成果；只替换当前目录，绝不改动历史目录。

    当前目录中的同名文件优先。先在同卷临时目录完成复制，再切换目录；
    切换失败恢复当前目录。调用方必须在用户修改动作中调用，浏览不调用。
    """
    import os
    import shutil
    import tempfile
    from file_cache import remove_temporary_tree
    from stage_path_service import existing_dir
    root = Path(project).resolve()
    target = write_dir(root, stage)
    origin = Path(source) if source is not None else existing_dir(root, stage)
    origin = origin.resolve()
    if not origin.is_relative_to(root) or origin == root:
        raise ValueError('历史阶段目录超出当前项目')
    if target.is_symlink() or target.resolve() != target or not target.is_relative_to(root):
        raise ValueError('阶段写入目录不能是目录联接或符号链接')
    if origin == target or not origin.is_dir():
        return target
    if target.is_relative_to(origin) or origin.is_relative_to(target):
        raise ValueError('历史与当前阶段目录不能互相包含')
    temporary = Path(tempfile.mkdtemp(prefix='.stage-copy-', dir=root))
    prepared = temporary / 'prepared'
    backup = temporary / 'previous'
    prepared.mkdir()

    def copy_files(folder, *, missing_only):
        for current, directories, files in os.walk(folder, followlinks=False):
            current = Path(current)
            for name in directories + files:
                item = current / name
                if item.is_symlink() or item.resolve() != item:
                    raise ValueError('历史阶段含目录联接或符号链接，未复制')
            relative = current.relative_to(folder)
            (prepared / relative).mkdir(parents=True, exist_ok=True)
            for name in files:
                item, destination = current / name, prepared / relative / name
                if missing_only and destination.exists():
                    continue
                before = item.stat()
                shutil.copy2(item, destination)
                after = item.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('复制期间历史文件变化，请停止相关编辑后重试')

    try:
        if target.is_dir():
            copy_files(target, missing_only=False)
        copy_files(origin, missing_only=True)
        if target.exists():
            target.replace(backup)
        try:
            prepared.replace(target)
        except Exception:
            if backup.exists():
                backup.replace(target)
            raise
    finally:
        # Only this call's unpublished scratch / redundant backup is removed.
        # A failed rollback leaves its backup intact for recovery.
        if not backup.exists() or target.exists():
            remove_temporary_tree(temporary)
    return target


def prepare_asset_write(project, base=None):
    from asset_context import library_dir
    from stage_path_service import LEGACY_NUMBERED
    root = Path(project).resolve()
    base = library_dir(root, base)
    # 本轮编号升级不迁移用户另行配置的资产库，保留既有自定义目录契约。
    if base != root / LEGACY_NUMBERED['assets']:
        return base
    return prepare_stage_write(root, 'assets', source=base)


def prepare_legacy_asset_base(base):
    """兼容仍只接收资产库路径的 UI 操作；不推测自定义目录所属项目。"""
    from stage_path_service import LEGACY_NUMBERED
    base = Path(base).resolve()
    if base.name == LEGACY_NUMBERED['assets']:
        return prepare_asset_write(base.parent, base)
    return base


def prepare_legacy_stage_path(path):
    """将显式修改目标重定位到新编号，历史文件保持只读。

    仅识别权威表中的完整旧目录名，不迁移普通目录或英文自定义目录。
    调用方保留空 source 的既有回退语义。
    """
    from stage_path_service import LEGACY_NUMBERED
    if path is None:
        return None
    target = Path(path).absolute()
    stages = {name: stage for stage, name in LEGACY_NUMBERED.items()}
    for ancestor in (target, *target.parents):
        stage = stages.get(ancestor.name)
        if stage is not None:
            current = prepare_stage_write(ancestor.parent, stage, source=ancestor)
            return current / target.relative_to(ancestor)
    return path


def save_writing_production_locks(project, values, *, attachment_signature=None):
    """制作锁与已存在的简报作为一包发布，失败不留下两份不同值。"""
    from copy import deepcopy
    from idea_chat import brief_complete_path
    from script_contract import PRODUCTION_LOCK_DEFINITIONS
    allowed = {item['key'] for item in PRODUCTION_LOCK_DEFINITIONS}
    if set(values) - allowed:
        raise ValueError('未知制作锁字段')
    updates = {key: str(value).strip() for key, value in values.items()}
    from script_contract import validate_production_locks
    validate_production_locks(updates)
    config_path = stage_config.path(project)
    config = deepcopy(file_cache.read_json(config_path) or {})
    workflow = config.get('workflow') or {}
    name = str(workflow.get('name') or '').strip()
    if not name:
        raise ValueError('请先在阶段配置选择总控')
    locks = stage_config.workflow_lock(project)
    locks.update(updates)
    workflow.setdefault('lock', {})[name] = locks
    if attachment_signature is not None:
        workflow.setdefault('lock_attachment_signatures', {})[name] = attachment_signature
    config['workflow'] = workflow
    documents = {config_path: config}
    brief_path = brief_complete_path(project_context(project))
    if brief_path.is_file():
        brief = deepcopy(file_cache.read_json(brief_path))
        brief['brief'].setdefault('production_locks', {}).update(updates)
        documents[brief_path] = brief
    payload = {path: json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
               for path, value in documents.items() if value != file_cache.read_json(path)}
    if payload:
        publish_stage_bundle(payload, lambda items: all(raw for _, raw in items),
                             lambda: stage_config._invalidate_cache(project))


def sync_writing_attachment_locks(project, *, reference=None):
    """仅在附档制作参数变化时同步，保留随后手动修订的值。"""
    from hashlib import sha256
    from idea_brief_form import extract_brief_creation
    from script_contract import PRODUCTION_LOCK_DEFINITIONS
    workflow = stage_config.current_workflow(project)
    name = str(workflow.get('name') or '').strip()
    if not name:
        return
    if reference is None:
        from idea_attachments import brief_sources
        reference = brief_sources(project_context(project),
                                  {'paths': stage_idea_attachment_paths(project, limit=3)})
    definitions = PRODUCTION_LOCK_DEFINITIONS
    labels = tuple(label for item in definitions
                   for label in (item['label'], *item.get('aliases', ()), item['key']))
    values = {}
    for text in reference.get('brief_texts', ()):
        fields = extract_brief_creation(text, extra_labels=labels, include_extra=True)
        for item in definitions:
            for label in (item['label'], *item.get('aliases', ()), item['key']):
                if fields.get(label, '').strip():
                    values.setdefault(item['key'], fields[label].strip())
                    break
    if not values:
        return
    signature = sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    if workflow.get('lock_attachment_signatures', {}).get(name) != signature:
        save_writing_production_locks(project, values, attachment_signature=signature)


def storyboard_adoption_impact(project, paths):
    """L3 注入项目上下文：候选分镜相对已采用分镜的只读影响预览。"""
    from storyboard_catalog_service import adoption_impact
    return adoption_impact(project_context(project), paths)


def asset_impact(project, aid, *, episode_dir=''):
    """L3 门面：资产变更影响视图（只读）。"""
    from asset_plan import asset_impact as _impact
    return _impact(project, aid, episode_dir=episode_dir)


def asset_deletion_references(project, aid, *, episode_dir=''):
    """L3 门面：删除资产前要先看的引用清单（只读）。"""
    from asset_plan import deletion_references as _references
    return _references(project, aid, episode_dir=episode_dir)


def continuity_issue_report(project, ledger=None):
    """L3 门面：连贯性问题闭环视图（只读，不落盘）。"""
    from continuity_ledger import issues, merge_issues, read_issues
    from continuity_ledger import read as read_ledger
    data = ledger if isinstance(ledger, dict) and ledger else read_ledger(project)
    _register, rows = merge_issues(read_issues(project), issues(data))
    return rows


def sync_continuity_issues(project, ledger=None):
    """L3 门面：算一遍问题并落盘 03_continuity/output/continuity_issues.json。"""
    from agent.core import save
    from continuity_ledger import read as read_ledger
    from continuity_ledger import sync_issues
    data = ledger if isinstance(ledger, dict) and ledger else read_ledger(project)
    return sync_issues(project, data, publish=save)


def decide_continuity_issue(project, issue_id, decision, reason='', by='人工'):
    """L3 门面：记一条问题的处理决定（忽略必须写理由）。"""
    from agent.core import save
    from continuity_ledger import decide_issue
    return decide_issue(project, issue_id, decision, reason, by=by, publish=save)


def animatic_preview_spec(project):
    """预演低清规格：画幅跟项目制作锁，分辨率与帧率保持低配；与正式交付规格同源。"""
    import stage_config
    from script_contract import preview_spec
    return preview_spec(stage_config.workflow_lock(Path(project)))


def publish_response_archive(project, text):
    """把模型已返回的可见正文归档到 01剧本准备/responses/，返回归档路径。

    只归档，不登记为阶段成果，也不改变采用状态；取消、迟到返回或格式不合格的
    正文同样留副本，供用户对照「原始响应已保存」。空正文不建文件。
    """
    from datetime import datetime
    from uuid import uuid4
    from stage_path_service import write_dir
    value = str(text or '').replace('\r\n', '\n')
    if not value.strip():
        return ''
    target = write_dir(project, 'script') / 'responses' / (
        datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid4().hex + '.txt')
    publish_stage_text(target, value, lambda published: published == value, lambda _target: None)
    return str(target)


def import_downloaded_creatives(context, provider='', model=''):
    """L3 编排：从本机「下载」文件夹收回桌面 Agent 窗口给出的同项目创作文件并发布。"""
    from idea_chat import import_downloaded_documents
    from platform_tools import downloads_directory
    return import_downloaded_documents(context, downloads_directory(), provider=provider, model=model,
                                       publish=publish_idea_creative)


DOWNLOAD_INBOX_LEDGER = ('工作流任务', '下载收件箱.json')


def _download_inbox_path(project):
    return Path(project).resolve().joinpath(*DOWNLOAD_INBOX_LEDGER)


def register_download_inbox(project, prompt, now=None):
    """L3 编排：登记一次桌面 Agent 任务书里的目标文件，供之后从下载文件夹收回。"""
    import time
    from agent.core import save
    from download_inbox import expected_targets, remaining
    now = time.time() if now is None else now
    targets = expected_targets(project, prompt)
    if not targets:
        return ()
    ledger = _download_inbox_path(project)
    try:
        current = file_cache.read_json(ledger) if ledger.is_file() else {}
    except (OSError, ValueError):
        current = {}
    pending = current.get('pending', []) if isinstance(current, dict) else []
    names = {str(target) for target in targets}
    pending = [entry for entry in remaining(pending, (), now)
               if str(entry.get('target')) not in names]
    pending.extend({'target': str(target), 'since': now} for target in targets)
    save(ledger, {'version': 1, 'pending': pending})
    return targets


def collect_download_inbox(project, now=None, downloads=None):
    """L3 编排：把已下载到「下载」文件夹的目标文件收回项目；返回已写入的目标路径。"""
    import time
    from agent.core import save, save_bytes
    from download_inbox import match, remaining
    ledger = _download_inbox_path(project)
    if not ledger.is_file():
        return []
    now = time.time() if now is None else now
    try:
        current = file_cache.read_json(ledger)
    except (OSError, ValueError):
        return []
    pending = current.get('pending', []) if isinstance(current, dict) else []
    if downloads is None:
        from platform_tools import downloads_directory
        downloads = downloads_directory()
    done = []
    for source, target in match(downloads, pending, now):
        try:
            data = source.read_bytes()
        except OSError:
            continue
        if not data:
            continue
        save_bytes(target, data)
        done.append(target)
    kept = remaining(pending, done, now)
    if kept != pending:
        save(ledger, {'version': 1, 'pending': kept})
    return done


def storyboard_catalog_snapshot(project, ignored=None):
    from storyboard_catalog_service import catalog_snapshot
    context = project_context(project)
    return catalog_snapshot(context) if ignored is None else catalog_snapshot(context, ignored)
