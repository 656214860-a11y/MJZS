"""阶段执行所需的编排器与上下文，不依赖配置面板。"""
import infra.app_logging as app_logging
import json
from pathlib import Path

import infra.file_cache as file_cache
import infra.model_pool as model_pool
import infra.model_router as model_router
import orchestrator.skill_budget as skill_budget
import orchestrator.stage_config as stage_config
import orchestrator.stage_models as stage_models
from orchestrator.project_context_factory import project_context
from contract.stage_path_service import write_dir
from orchestrator.stage_asset_gateways import (  # noqa: F401  re-export
    _json_gateway,
    asset_batch_gateway,
    asset_plan_gateway,
    sync_asset_plan,
    update_asset_plan_fields,
    apply_asset_plan_gate_choice,
    plan_unattended_assets,
    note_asset_resume_round,
    adopt_asset_storyboards,
    remove_asset_storyboards,
    poll_asset_storyboard_adoption,
    release_uncertain_asset_batch,
    asset_detail_gateway,
    bind_asset_canonical_view,
    bind_asset_variant_thumbnail,
    pending_generated_assets,
    import_pending_generated_assets,
    unwrap_service_result)
from orchestrator.stage_animatic_gateways import animatic_reference_paths, animatic_video, confirm_animatic, generate_animatic_reference, import_animatic_audio, import_animatic_references, publish_animatic_bundle, run_animatic
from orchestrator.stage_previs_gateways import dispatch_stage_previs, install_stage_previs_progress, previs_automatic_candidates, previs_automatic_engine, previs_entries, previs_progress_gateway, previs_ready, previs_records_directory, previs_routing_gateway, publish_stage_previs_progress, save_stage_previs_override, storyboard_board_source_script, storyboard_catalog, storyboard_catalog_snapshot, storyboard_default_source, storyboard_document_dir, storyboard_file_snapshot, storyboard_produced_episodes, storyboard_produced_scripts, storyboard_resolve_source, storyboard_working_dir
from orchestrator.stage_gate_gateways import cloud_video_gateway, cloud_video_saved_provider_key, cloud_video_session_folder, media_import_publisher, publish_cloud_video_session_config, publish_cloud_video_studio_config, publish_cloud_video_workspace_preference, publish_tts_full_track, refresh_audio_manifests, reusable_tts_full_track, run_tts_lines, save_tts_key, tts_gateway, video_lifecycle_gateway


def release_tts_unknown(folder, indexes):
    """L3：人工放开逐句配音结果未知的句子（sending／uncertain／unsaved → failed）。"""
    from domain.tts_api import release_unknown
    return release_unknown(folder, indexes, gateway=tts_gateway())


def reserve_tts_full_track(project, signature, confirmed=False, confirm=None):
    """L3：整段配音预约「指纹＋尝试序号」请求号；上次结果未知须经 confirm 放行。"""
    from domain.tts_api import reserve_full_track_attempt
    return reserve_full_track_attempt(project_context(project), signature,
                                      confirmed=confirmed, confirm=confirm, gateway=tts_gateway())


def synthesize_tts_full_track(project, text, signature, request_id, settings=None):
    """L3：整段配音发送并把确定失败／结果未知回写尝试账，异常原样上抛。"""
    from domain.tts_api import synthesize_full_track
    return synthesize_full_track(project_context(project), text, signature, request_id,
                                 settings=settings, gateway=tts_gateway())
from orchestrator.stage_handoff_gateways import (  # noqa: F401  re-export
    asset_impact,
    continuity_issue_report,
    decide_continuity_issue,
    import_downloaded_creatives,
    mark_stage_video_deleted,
    publish_handoff_bundle,
    publish_idea_creative,
    publish_response_archive,
    publish_writing_preparation,
    save_automatic_assemble_marker,
    save_automatic_handoff_marker,
    save_stage_editing_checklist,
    save_stage_video_options,
    save_stage_white_model_upload,
    storyboard_adoption_impact,
    sync_continuity_issues,
    verify_handoff_bundle)
from orchestrator.stage_publication import (
    project_registry_gateway,
    publish_stage_bundle,
    publish_stage_bytes,
    publish_stage_text,
    recover_stage_publications)
from orchestrator.stage_write_preparation_service import prepare_asset_write, prepare_legacy_asset_base, prepare_legacy_stage_path, prepare_stage_write
from orchestrator.stage_download_inbox_service import collect_download_inbox, register_download_inbox
















def program_of(desktop):
    return getattr(desktop, 'app', None) or None


def keyframe_image_prompt(project, source, shot_id=None, outputs=None, shot_ids=None):
    """L3 为首帧批次任务书注入唯一的项目上下文。"""
    from domain.keyframe_batch import image_prompt
    return image_prompt(source, project_context(project), shot_id, outputs, shot_ids=shot_ids)


def import_delivery_master(project, source, *, settings_snapshot=None, cache=None):
    """交付成片导入编排：L3 负责上下文和发布器注入。"""
    from domain.delivery_import_service import import_final_master
    return import_final_master(
        project_context(project, settings_snapshot=settings_snapshot, cache=cache), source,
        publish=media_import_publisher(project, 'video'))




def local_video_settings_gateway():
    """L3 为本地视频设置服务注入唯一的发布与回滚能力。"""
    import shutil
    from agent.core import replace, save, save_bytes
    return {'publish_json': save, 'publish_bytes': save_bytes,
            'copy_file': shutil.copy2, 'replace_file': replace,
            'published': file_cache.published}


def publish_local_video_settings(project, current_config, options):
    """L3 编排本地视频工作流与项目设置的成对发布。"""
    from domain.local_video_settings_service import save_local_video_settings
    return save_local_video_settings(project_context(project), current_config, options,
                                     gateway=local_video_settings_gateway())


def pet_performance_gateway():
    """L3 为宠物优化账本装配唯一的 JSON 发布器。"""
    return _json_gateway()


def start_pet_performance_check(program, project, kind='startup'):
    """L3 编排宠物离线基准启动；L4 不直接调用 L2 服务。"""
    from domain.pet_performance_service import (start_hotspot_check, start_long_list_check,
                                         start_startup_check)
    starters = {'long_list': start_long_list_check, 'hotspot': start_hotspot_check}
    return starters.get(kind, start_startup_check)(program, project)


def poll_pet_performance_check(session, at=None):
    """L3 轮询宠物离线基准，并向 L2 注入正式账本发布器。"""
    from domain.pet_performance_service import poll_startup_check
    return poll_startup_check(session, project_context(session['project']), at=at,
                              publish=pet_performance_gateway()['publish_json'])


def pet_test_gateway():
    """L3 为宠物增量自检账本装配唯一的 JSON 发布器。"""
    return _json_gateway()


def start_pet_test_check(program, text=''):
    """L3 编排宠物增量自检启动；L4 不直接调用 L2 服务。"""
    from domain.pet_test_service import start_incremental
    return start_incremental(program, text)


def poll_pet_test_check(session, project, at=None):
    """L3 轮询宠物增量自检，并向 L2 注入正式账本发布器。"""
    from domain.pet_test_service import poll_incremental
    return poll_incremental(session, project_context(project), at=at,
                            publish=pet_test_gateway()['publish_json'])


def import_stage_audio(project, source):
    """音频导入编排：导入成功后刷新配音字幕清单。"""
    result = _import_audio_file(project, source)
    if result.ok:
        refresh_audio_manifests(project)
    return result


def _import_audio_file(project, source):
    """音频导入编排：L3 注入校验与有界文件发布器。"""
    from domain.audio_import_service import import_audio
    return import_audio(project, source, publish=media_import_publisher(project, 'audio'))






def export_stage_srt(project, episode):
    """字幕导出编排：L3 注入统一文本阶段发布器。"""
    from domain.subtitle_export_service import export_srt
    result = export_srt(project, episode, publish=publish_stage_text)
    if result.ok:
        refresh_audio_manifests(project)
    return result


def video_prompt_gateway():
    """L3 为视频提示词草稿与可见成果装配事务发布能力。"""
    from agent.core import restore_bytes, save, save_bytes
    return {'publish_bundle': publish_stage_bundle,
            'read_bytes': lambda path: Path(path).read_bytes(),
            'publish_json': save, 'publish_bytes': save_bytes,
            'restore_bytes': restore_bytes,
            'remove_dir': lambda folder: Path(folder).rmdir()}


def publish_video_prompt(studio, sid, text):
    from domain.video_prompt_publication import publish
    result = publish(studio, sid, text, publish_bundle=video_prompt_gateway()['publish_bundle'])
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def import_video_prompt(studio, sid, text):
    from domain.video_prompt_publication import stage_import
    result = stage_import(studio, sid, text, gateway=video_prompt_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def export_stage_dialogue_script(project, episode, assets):
    """对白脚本导出编排：L3 注入统一文本阶段发布器。"""
    from domain.subtitle_export_service import export_dialogue_script
    result = export_dialogue_script(project, episode, assets, publish=publish_stage_text)
    if result.ok:
        refresh_audio_manifests(project)
    return result


def adopt_natural_script(project, source_path):
    """为显式采用的自然剧本版本注入统一发布器。"""
    from domain.script_workspace_service import adopt_natural_script as adopt
    return adopt(project, source_path, publish=publish_stage_text)


def restart_writing_preparation(project, stage):
    """显式重写入口复用阶段发布器，不由桌面直接写确认台账。"""
    from writing_api import restart_preparation
    return restart_preparation(project, stage, publish=publish_stage_text)
def confirm_writing_preparation(project, stage, path):
    """显式把当前文件登记为该阶段确认输出的编排入口，复用统一阶段发布器。"""
    from orchestrator.writing_unconfirm import confirm_preparation_document
    return confirm_preparation_document(project, stage, path, publish=publish_stage_text)


def unconfirm_writing_preparation(project, stage):
    """显式取消该阶段确认并把准备流程回退到该阶段的编排入口，复用统一阶段发布器。"""
    from orchestrator.writing_unconfirm import unconfirm_preparation_document
    return unconfirm_preparation_document(project, stage, publish=publish_stage_text)


def apply_partial_adoption(project, stage, path, keep):
    """按段落采用编排入口：截写所选段落并登记标记，复用统一阶段发布器。"""
    from orchestrator.writing_unconfirm import apply_partial_adoption as apply_adoption
    return apply_adoption(project, stage, path, keep, publish=publish_stage_text)


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
    from domain.writing_quality import split_response, publish_reports
    from contract.stage_path_service import write_dir
    target = Path(script_path)
    folder = write_dir(project, 'script').resolve()
    if not target.resolve().is_relative_to(folder):
        raise ValueError('质检仅回收当前剧本准备目录内的文件')
    before = target.stat()
    response = target.read_text(encoding='utf-8')
    body, _, _ = split_response(response)
    body = str(body or '').strip()
    result = publish_reports(response, target, folder / 'quality', publish=publish_stage_text).data
    after = target.stat()
    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise ValueError('回收期间正文变化，请等待本轮写入完成')
    # 只要正文被剥离出附块（无论附块是否闭合、是否损坏），都写回干净正文，
    # 避免半截 <script_quality> JSON 残留在自然剧本文件末尾。
    if response.strip() != body.strip():
        publish_stage_text(target, body.strip() + '\n', lambda value: bool(str(value).strip()), lambda _target: None)
    return dict(result, text=body, natural_script_path=str(target))


def desktop_settings_gateway():
    """L3 为桌面级偏好设置注入唯一 JSON 发布器。"""
    return _json_gateway()


def publish_desktop_preferences(settings_path, current, updates):
    """桌面设置持久化只经 L3 装配的发布器。"""
    from domain.desktop_settings_service import publish_desktop_settings
    return publish_desktop_settings(settings_path, current, updates,
                                    publish=desktop_settings_gateway()['publish_json'])


def legacy_adoption_gateway():
    """L3 为旧目录归位记录装配目录与 JSON 发布能力。"""
    return _json_gateway(make_dir=lambda folder: Path(folder).mkdir(parents=True, exist_ok=True))


def record_stage_legacy_adoption(project, linked_paths, now=None):
    """旧目录归位记录只经 L3 网关发布。"""
    from domain.legacy_adoption_service import record_legacy_adoption
    result = record_legacy_adoption(project, linked_paths, now=now,
                                    gateway=legacy_adoption_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def idea_attachment_local_mode(project):
    """显式 API 选择优先；其余按 writing 实际目标识别本地 Agent。"""
    import infra.model_pool as model_pool
    from orchestrator.workflow_engines import current_config
    import writing_api
    if writing_api.model_label(project):
        return False
    config = current_config(project, 'writing')
    engine = model_pool.desktop_engine(config.get('model')) or config.get('engine')
    return engine in {'codex', 'claude', 'qwen', 'opencode', 'client-cli'} and not config.get('api')


def archive_idea_attachments(project, paths, now=None):
    """剧本准备附档归档编排：L3 注入统一文本阶段发布器。"""
    from domain.idea_attachments import store

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
    from domain.idea_attachments import uploaded
    return uploaded(project_context(project), limit, local_mode=idea_attachment_local_mode(project))


def stage_idea_attachment_reference(project, message='', selected_paths=()):
    """为剧本准备对话解析已入库附档，不向 L2 暴露裸项目路径。"""
    from domain.idea_attachments import referenced, brief_sources
    from orchestrator.workflow_engines import current_config
    context = project_context(project)
    local_mode = idea_attachment_local_mode(project)
    result = referenced(context, message, selected_paths,
                        local_mode=local_mode, markdown_only=local_mode and
                        current_config(project, 'writing').get('engine') == 'claude')
    result.update(brief_sources(context, result))
    return result


def prepare_idea_attachment_selection(project, paths):
    """仅预检刚上传的附件，不把历史最近三份混入上传结果。"""
    from domain.idea_attachments import prepare
    return prepare(paths, local_mode=idea_attachment_local_mode(project), context=project_context(project))


def stage_idea_brief_defaults(project, *, reference=None):
    """复用本轮引用的解析副本，不再扫描目录或改变模型投递上下文。"""
    from domain.idea_brief_form import extract_brief_creation
    if reference is None:
        reference = stage_idea_attachment_reference(project)
    values = {}
    for text in reference.get('brief_texts', ()):
        fields = extract_brief_creation(text)
        for label, value in fields.items():
            values.setdefault(label, value)
    return {'values': values, 'skipped': reference.get('brief_unreadable', ())}


def prepare_idea_semantic_brief(project, draft, reference):
    from orchestrator.idea_semantic_brief_service import semantic_brief_request
    return semantic_brief_request(project_context(project), draft, reference,
                                  local_mode=idea_attachment_local_mode(project))


def validate_idea_semantic_sources(request):
    for source, modified, size in request['fingerprints']:
        stat = source.stat()
        if (stat.st_mtime_ns, stat.st_size) != (modified, size):
            raise ValueError('附档内容已变化，未套用旧提取结果，请重新发送。')


def read_idea_semantic_brief(request):
    """只轮询本次唯一文件；模型尚未原子发布时继续等待。"""
    from orchestrator.idea_semantic_brief_service import SEMANTIC_BRIEF_MAX_BYTES, semantic_brief_values
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
    from infra.storage_maintenance import recycle_paths
    return {
        'read_json': file_cache.read_json,
        'publish_json': save,
        'publish_text': save_text,
        'recycle_paths': recycle_paths,
    }


def asset_batch_settings_gateway():
    """L3 为资产批量设置服务注入唯一的项目设置发布器。"""
    return _json_gateway()


def save_asset_batch_settings(project, options, categories=None, restored_model_id=None):
    from domain.asset_batch_settings_service import save_settings
    return save_settings(project, options, categories, restored_model_id,
                         publish=asset_batch_settings_gateway()['publish_json'])


def remove_asset_batch_model(project, url, model, model_id):
    from domain.asset_batch_settings_service import remove_model
    return remove_model(project, url, model, model_id,
                        publish=asset_batch_settings_gateway()['publish_json'])










def storyboard_working_source(project, source):
    """L3 为分镜生命周期的工作稿判定注入项目上下文。"""
    from domain.storyboard_lifecycle import is_working_source
    return is_working_source(project_context(project), source)


def retire_storyboard(project, source, target, expected, publish):
    """L3 为已发布定稿退役工作分镜注入项目上下文。"""
    from domain.storyboard_lifecycle import retire
    return retire(project_context(project), source, target, expected, publish=publish)


def refresh_storyboard_studios(desktop, project):
    """L3 为定稿后的已开分镜工作集刷新注入项目上下文。"""
    from domain.storyboard_lifecycle import refresh_open_studios
    return refresh_open_studios(desktop, project_context(project))


def white_model_shot_directory(project, sid, workspace_path=None, source=None):
    """L3 为白模镜头工作目录解析注入项目上下文；source 明确本次是哪一集。"""
    from domain.white_model_service import shot_directory
    return shot_directory(project_context(project), sid, workspace_path, source)


def migrate_white_model_directories(project):
    """L3 为白模旧目录迁移注入项目上下文与正式发布器。"""
    from agent.core import save
    from domain.white_model_service import migrate_legacy_directories
    return migrate_legacy_directories(project_context(project), publish=save)


















def confirm_gates_gateway():
    """L3 为确认门禁注入唯一的正式 JSON 发布器。"""
    return _json_gateway()


def record_stage_confirmation(project, key, choice='', by='human', state='applied', digest=''):
    """记录确认门禁；L4 不得自行装配或直写确认账本。state 见 confirm_gates.record。"""
    from domain.confirm_gates import record
    return record(project, key, choice, by=by, state=state, digest=digest,
                  publish=confirm_gates_gateway()['publish_json'],
                  context=project_context(project))


def forget_stage_confirmation(project, key):
    """撤销确认门禁；保持与记录入口相同的 L3 发布边界。"""
    from domain.confirm_gates import forget
    return forget(project, key, publish=confirm_gates_gateway()['publish_json'],
                  context=project_context(project))


def adopt_asset_plan_choice(project, key, choice, digest=''):
    """准备→落盘→确认走完一条路：只有落盘成功才把确认记成 applied。

    先记 pending：进程中断只留下 pending，候选会重新摆出、可再点一次；落盘失败记 failed，
    同样不算确认完成。任何一步没走完，都不会出现「未采用却已审核通过」（O10）。
    """
    from domain.confirm_gates import APPLIED, FAILED, PENDING
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
    from domain.confirm_gates import run
    return run(gate_id, project=project, shots=shots, assets=assets, ledger=ledger,
               context=project_context(project))












def record_previs_evidence(project, sid, source, media=None):
    """L3 为白模就绪登记注入项目上下文与正式发布器。"""
    from agent.core import save
    from domain.white_model_service import record_evidence
    root = white_model_shot_directory(project, sid, source=source)
    return _with_previs_copy(record_evidence(root, sid, source, publish=save, media=media), project, sid, source)
































def storyboard_edit_gateway():
    """L3 为定稿分镜编辑服务注入唯一的 JSON 发布器。"""
    return _json_gateway()


def save_edited_stage_storyboard(path, data):
    """保存已校验的定稿分镜；L3 保持正式发布器唯一装配点。"""
    from domain.storyboard_edit_service import save_edited_json
    return save_edited_json(prepare_legacy_stage_path(path), data,
                            publish=storyboard_edit_gateway()['publish_json'])


def storyboard_gateway():
    from agent.core import save, save_bytes
    from infra.file_cache import remove_temporary_file
    from agent.core import save_bytes_new
    from infra.storage_maintenance import recycle_paths
    return {'publish_json': save, 'publish_bytes': save_bytes, 'publish_bytes_new': save_bytes_new,
            'recycle_paths': recycle_paths,
            'remove_temporary_file': remove_temporary_file}


def publish_final_storyboard_bundle(episodefile, assetfile, episode, assets, validate):
    from domain.storyboard_storage import publish_final_bundle
    return unwrap_service_result(publish_final_bundle(episodefile, assetfile, episode, assets, validate,
                                                       gateway=storyboard_gateway()))


def normalize_storyboard_for_desktop(desktop):
    from domain.storyboard_storage import normalize_for_desktop
    return unwrap_service_result(normalize_for_desktop(desktop, gateway=storyboard_gateway()))
















def publish_keyframe_episode(target, episode):
    """由 L3 原子发布首帧索引 JSON，供首帧生命周期服务注入。"""
    return publish_stage_text(
        target, json.dumps(episode, ensure_ascii=False, indent=2),
        lambda value: isinstance(json.loads(value), dict), lambda _target: None)


def delete_stage_keyframe(base, source, episode, shot):
    """首帧删除编排：L3 注入索引发布器。"""
    from domain.keyframe_lifecycle_service import delete_keyframe
    return delete_keyframe(prepare_legacy_stage_path(base), prepare_legacy_stage_path(source), episode, shot, publish=publish_keyframe_episode)


def restore_stage_keyframe(base, source, episode, shot):
    """首帧恢复编排：L3 注入索引发布器。"""
    from domain.keyframe_lifecycle_service import restore_keyframe
    return restore_keyframe(prepare_legacy_stage_path(base), prepare_legacy_stage_path(source), episode, shot, publish=publish_keyframe_episode)


def replace_stage_keyframe(base, source, episode, shot, data):
    """首帧替换编排：L3 注入图片与索引两个原子发布器。"""
    from domain.keyframe_lifecycle_service import replace_keyframe
    return replace_keyframe(
        prepare_legacy_stage_path(base), prepare_legacy_stage_path(source), episode, shot, data, publish=publish_stage_bytes,
        publish_episode=publish_keyframe_episode)






def publish_stage_handoff_bundle(project, shots, rows, subtitle=None, auto=False):
    """交接包编排：L3 注入项目上下文与唯一阶段发布器。"""
    from domain.handoff_service import publish_bundle
    result = publish_bundle(project, shots, rows, subtitle, auto,
                            publish=publish_handoff_bundle,
                            context=project_context(project))
    if not result.ok:
        raise ValueError(result.reason)
    return result.data




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
    import orchestrator.skill_orchestrator as skill_orchestrator
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


def import_writing_project(root, json_file):
    """L3 编排剧本 JSON 导入与其校验报告发布。"""
    from domain.writing import import_project
    from orchestrator.workflow_context_controller import workflow_context_gateway
    result = import_project(root, json_file, gateway=project_registry_gateway(),
                            publish_report=workflow_context_gateway()['publish_json'])
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def prepare_writing_project(root, brief, stage, target):
    """L3 编排剧本任务书发布并只向界面交付成功数据。"""
    from domain.writing import prepare
    result = prepare(root, brief, stage, target, publish=publish_writing_preparation)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


unwrap_project_result = unwrap_service_result


def require_formal_asset_generation(project, *, online_model):
    """生成正式资产前核验 SG-B 与线上模型；纯计划和浏览不受影响。"""
    import orchestrator.stage_parallel as stage_parallel
    gate = stage_parallel.evaluate(project, 'assets')
    if not gate['ok']:
        raise ValueError(stage_parallel.blocked_text(gate))
    if not online_model:
        raise ValueError('正式资产请选择线上 API 模型；本地草图请在分镜预演阶段生成')


def save_writing_production_locks(project, values, *, attachment_signature=None):
    """制作锁与已存在的简报作为一包发布，失败不留下两份不同值。"""
    from copy import deepcopy
    from domain.idea_chat import brief_complete_path
    from contract.script_contract import PRODUCTION_LOCK_DEFINITIONS
    allowed = {item['key'] for item in PRODUCTION_LOCK_DEFINITIONS}
    if set(values) - allowed:
        raise ValueError('未知制作锁字段')
    updates = {key: str(value).strip() for key, value in values.items()}
    from contract.script_contract import validate_production_locks
    validate_production_locks(updates)
    config_path = stage_config.path(project)
    config = deepcopy(stage_config._workflow_data(project))
    locks = stage_config.workflow_lock(project)
    locks.update(updates)
    config['production_locks'] = {key: value for key, value in locks.items() if str(value or '').strip()}
    if attachment_signature is not None:
        config['production_lock_attachment_signature'] = attachment_signature
    documents = {config_path: config}
    brief_path = brief_complete_path(project_context(project))
    if brief_path.is_file():
        brief = deepcopy(file_cache.read_json(brief_path))
        brief['brief'].setdefault('production_locks', {}).update(updates)
        documents[brief_path] = brief
    payload = {path: json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
               for path, value in documents.items()
               if value != (file_cache.read_json(path) if Path(path).is_file() else None)}
    if payload:
        publish_stage_bundle(payload, lambda items: all(raw for _, raw in items),
                             lambda: stage_config._invalidate_cache(project))


def sync_writing_attachment_locks(project, *, reference=None):
    """仅在附档制作参数变化时同步，保留随后手动修订的值。"""
    from hashlib import sha256
    from domain.idea_brief_form import extract_brief_creation
    from contract.script_contract import PRODUCTION_LOCK_DEFINITIONS
    data = stage_config._workflow_data(project)
    if reference is None:
        from domain.idea_attachments import brief_sources
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
    if data.get('production_lock_attachment_signature') != signature:
        save_writing_production_locks(project, values, attachment_signature=signature)


















def sync_previs_copy(project, sid, source):
    """已校验的预演在项目内留副本并登记 previs.json；副本失败不否定已通过的校验。"""
    from agent.core import save
    from domain.white_model_service import sync_project_copy
    try:
        return sync_project_copy(project_context(project), sid, source, publish=save)
    except (OSError, ValueError):
        app_logging.swallowed('预演项目内副本未写入')
        return None


def _with_previs_copy(evidence, project, sid, source):
    sync_previs_copy(project, sid, source)
    return evidence
