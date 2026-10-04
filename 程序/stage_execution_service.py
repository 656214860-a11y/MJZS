"""阶段执行所需的编排器与上下文，不依赖配置面板。"""
import json
from pathlib import Path

import file_cache
import model_pool
import model_router
import skill_budget
import stage_config
import stage_models
from project_context import ProjectContext
from stage_path_service import write_dir


def program_of(desktop):
    return getattr(desktop, 'app', None) or None


def project_context(project, *, settings_snapshot=None, cache=None):
    """由 L3 装配项目根、阶段路径、设置快照和缓存给 L2 服务。"""
    root = Path(project)
    return ProjectContext.snapshot(
        root, lambda stage: write_dir(root, stage), settings_snapshot,
        file_cache if cache is None else cache)


def import_delivery_master(project, source, *, settings_snapshot=None, cache=None):
    """交付成片导入编排：L3 负责上下文和发布器注入。"""
    from delivery_import_service import import_final_master
    return import_final_master(
        project_context(project, settings_snapshot=settings_snapshot, cache=cache), source,
        publish=publish_stage_bytes)


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
    return save_local_video_settings(project, current_config, options,
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
    return poll_startup_check(session, at=at,
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
    return poll_incremental(session, project, at=at,
                            publish=pet_test_gateway()['publish_json'])


def import_stage_audio(project, source):
    """音频导入编排：L3 注入唯一二进制发布器。"""
    from audio_import_service import import_audio
    return import_audio(project, source, publish=publish_stage_bytes)


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


def reply_to_writing(project, creative, progress=None, cancelled=None, stream=None):
    """剧本模型调用编排：为所有可见剧本成果注入统一发布器。"""
    from writing_api import reply
    return reply(project, creative, progress=progress, cancelled=cancelled, stream=stream,
                 publish=publish_stage_text)


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


def archive_idea_attachments(project, paths, now=None):
    """剧本准备附档归档编排：L3 注入统一文本阶段发布器。"""
    from idea_attachments import store

    def publish_attachment(target, text):
        return publish_stage_text(
            target, text, lambda value: bool(value.strip()), lambda _target: None)

    result = store(project, paths, now=now, publish=publish_attachment)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def idea_chat_gateway():
    """为 ``idea_chat`` 注入缓存读取与原子发布；L2 不可自行落盘。"""
    from agent.core import save, save_text
    return {
        'read_json': file_cache.read_json,
        'publish_json': save,
        'publish_text': save_text,
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
    return sync_plan(project, episode_dir, storyboard, scope=scope, _adopting=_adopting,
                     gateway=asset_plan_gateway())


def update_asset_plan_fields(project, episode_dir, aid, values):
    from asset_plan import update_fields
    return update_fields(project, episode_dir, aid, values, gateway=asset_plan_gateway())


def apply_asset_plan_gate_choice(project, key, choice, episode_dir=''):
    from asset_plan import apply_gate_choice
    return apply_gate_choice(project, key, choice, episode_dir, gateway=asset_plan_gateway())


def plan_unattended_assets(project, base, sources, scope='adopted'):
    """L3 为无人值守资产计划装配唯一的发布网关。"""
    from asset_batch_service import unattended_plan
    return unattended_plan(project, base, sources, scope, gateway=asset_plan_gateway())


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
    return release_uncertain(project, ids, publish=asset_batch_gateway()['publish_json'])


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
    result = bind_canonical_view(project, episode_dir, aid, view, source,
                                gateway=asset_detail_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def bind_asset_variant_thumbnail(project, episode_dir, aid, state_id, source):
    """L3 编排资产详情状态变体缩略图绑定。"""
    from asset_detail_service import bind_variant_thumbnail
    result = bind_variant_thumbnail(project, episode_dir, aid, state_id, source,
                                   gateway=asset_detail_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def tts_gateway():
    """L3 为 TTS 服务装配唯一的正式发布器；L2 不可自行写设置或阶段成果。"""
    from agent.core import save, save_bytes
    return {'publish_json': save, 'publish_bytes': save_bytes}


def save_tts_key(base_url, model, voice, key, voices=None, speeds=None):
    from tts_api import save_key
    return save_key(base_url, model, voice, key, voices, speeds, gateway=tts_gateway())


def publish_tts_full_track(project, signature, raw):
    from tts_api import publish_full_track
    return publish_full_track(project, signature, raw, gateway=tts_gateway())


def run_tts_lines(lines, folder, generate=None, report=None, stop=None):
    from tts_api import run_lines
    return run_lines(lines, folder, generate, report, stop, gateway=tts_gateway())


def cloud_video_gateway():
    """L3 为云视频配置服务装配唯一的正式 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


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


def record_stage_confirmation(project, key, choice='', by='human'):
    """记录确认门禁；L4 不得自行装配或直写确认账本。"""
    from confirm_gates import record
    return record(project, key, choice, by=by,
                  publish=confirm_gates_gateway()['publish_json'])


def forget_stage_confirmation(project, key):
    """撤销确认门禁；保持与记录入口相同的 L3 发布边界。"""
    from confirm_gates import forget
    return forget(project, key, publish=confirm_gates_gateway()['publish_json'])


def previs_routing_gateway():
    """L3 为白模分流策略注入唯一的正式 JSON 发布器。"""
    from agent.core import save
    return {'publish_json': save}


def save_stage_previs_override(project, source, shot_id, value):
    """保存白模复杂度人工覆写；L4 只委托 L3。"""
    from previs_routing import set_override
    return set_override(project, source, shot_id, value,
                        publish=previs_routing_gateway()['publish_json'])


def dispatch_stage_previs(project, source, shot_ids, state, monitor=False, start_complex=None):
    """发布白模分流记录；执行器仍由调用方注入，路由落盘只经 L3。"""
    from previs_routing import dispatch
    return dispatch(project, source, shot_ids, state, monitor=monitor,
                    start_complex=start_complex,
                    publish=previs_routing_gateway()['publish_json'])


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
    return save_edited_json(path, data,
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
    return publish_final_bundle(episodefile, assetfile, episode, assets, validate,
                                gateway=storyboard_gateway())


def normalize_storyboard_for_desktop(desktop):
    from storyboard_storage import normalize_for_desktop
    return normalize_for_desktop(desktop, gateway=storyboard_gateway())


def mark_stage_video_deleted(source, sid, versions):
    from video_lifecycle_service import mark_video_deleted
    result = mark_video_deleted(source, sid, versions, gateway=video_lifecycle_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_stage_video_options(source, sid, selected, generate_audio, is_local):
    from video_lifecycle_service import save_video_options
    result = save_video_options(source, sid, selected, generate_audio, is_local,
                              gateway=video_lifecycle_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_stage_white_model_upload(source, sid, enabled):
    from video_lifecycle_service import save_white_model_upload
    result = save_white_model_upload(source, sid, enabled, gateway=video_lifecycle_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def save_stage_editing_checklist(project, text):
    """剪辑清单保存编排：保留用户清空清单的既有语义。"""
    from edit_service import save_editing_checklist

    def publish_checklist(target, value):
        return publish_stage_text(
            target, value, lambda _value: True, lambda _target: None, allow_empty=True)

    result = save_editing_checklist(project, text, publish=publish_checklist)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def publish_handoff_bundle(project, name, artifacts, *, auto=False):
    """交接包发布编排：L3 负责目录切换、字节发布与旧自动包回收。"""
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
    return delete_keyframe(base, source, episode, shot, publish=publish_keyframe_episode)


def restore_stage_keyframe(base, source, episode, shot):
    """首帧恢复编排：L3 注入索引发布器。"""
    from keyframe_lifecycle_service import restore_keyframe
    return restore_keyframe(base, source, episode, shot, publish=publish_keyframe_episode)


def replace_stage_keyframe(base, source, episode, shot, data):
    """首帧替换编排：L3 注入图片与索引两个原子发布器。"""
    from keyframe_lifecycle_service import replace_keyframe
    return replace_keyframe(
        base, source, episode, shot, data, publish=publish_stage_bytes,
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

    from agent.core import restore_bytes, save_text
    previous = target.read_bytes() if target.is_file() else None
    save_text(target, value, encoding=encoding)
    try:
        update_index(target)
    except Exception:
        restore_bytes(target, previous)
        raise
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

    from agent.core import restore_bytes, save_bytes
    previous = target.read_bytes() if target.is_file() else None
    save_bytes(target, value)
    try:
        update_index(target)
    except Exception:
        restore_bytes(target, previous)
        raise
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

    from agent.core import restore_bytes, save_bytes
    previous = {path: path.read_bytes() if path.is_file() else None for path, _data in items}
    try:
        for path, data in items:
            save_bytes(path, data)
        update_index()
    except Exception:
        for path, _data in reversed(items):
            restore_bytes(path, previous[path])
        raise
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
