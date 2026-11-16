"""L3 分镜预演与分镜查询网关：预演路由、进度发布与分镜来源查询入口装配。

自 stage_execution_service 拆出；那边按原名重新导出，旧调用点与测试补丁点不变。
"""
from project_context_factory import project_context
from orchestrator.stage_asset_gateways import _json_gateway


def previs_routing_gateway():
    """L3 为白模分流策略注入唯一的正式 JSON 发布器。"""
    return _json_gateway()


def save_stage_previs_override(project, source, shot_id, value):
    """保存白模复杂度人工覆写；L4 只委托 L3。"""
    from domain.previs_routing import set_override
    return set_override(project_context(project), source, shot_id, value,
                        publish=previs_routing_gateway()['publish_json'])


def dispatch_stage_previs(project, source, shot_ids, state, monitor=False, start_complex=None):
    """发布白模分流记录；执行器仍由调用方注入，路由落盘只经 L3。"""
    from domain.previs_routing import dispatch
    return dispatch(project_context(project), source, shot_ids, state, monitor=monitor,
                    start_complex=start_complex,
                    publish=previs_routing_gateway()['publish_json'])


def previs_entries(project, source):
    from domain.previs_routing import entries
    return entries(project_context(project), source)


def previs_ready(project, shot_id, source=None):
    from domain.previs_routing import ready
    return ready(project_context(project), shot_id, source)


def previs_records_directory(project, state):
    from domain.previs_routing import records_directory
    return records_directory(project_context(project), state)


def previs_automatic_candidates(project, source, shots, wait_for_frames=False, pending_frame_ids=None):
    from domain.previs_routing import automatic_candidates
    return automatic_candidates(project_context(project), source, shots, wait_for_frames, pending_frame_ids)


def previs_automatic_engine(project, read_settings, engines):
    from domain.previs_routing import automatic_engine
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
    from domain.previs_progress_service import publish
    return publish(path, shot_id, stage, completed, total,
                   publish_text=previs_progress_gateway()['publish_text'])


def install_stage_previs_progress(path, shot_id):
    """为 Blender 安装进度回调，并向 L2 注入正式发布器。"""
    from domain.previs_progress_service import install_blender_progress
    return install_blender_progress(path, shot_id,
                                    publish_text=previs_progress_gateway()['publish_text'])


def storyboard_catalog_snapshot(project, ignored=None):
    from storyboard_catalog_service import catalog_snapshot
    context = project_context(project)
    return catalog_snapshot(context) if ignored is None else catalog_snapshot(context, ignored)
