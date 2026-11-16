"""L3 资产阶段网关：资产批处理、计划、详情绑定与生成资产导入的唯一正式读写入口装配。

自 stage_execution_service 拆出；那边重新导出全部名字，旧调用点与测试补丁点不变。
"""
from pathlib import Path

import file_cache
from project_context_factory import project_context
from orchestrator.stage_write_preparation_service import prepare_asset_write


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
    from domain.asset_plan import sync_plan
    episode_dir = prepare_asset_write(project, episode_dir)
    return unwrap_service_result(sync_plan(project, episode_dir, storyboard, scope=scope, _adopting=_adopting,
                                            gateway=asset_plan_gateway(), context=project_context(project)))


def update_asset_plan_fields(project, episode_dir, aid, values):
    from domain.asset_plan import update_fields
    episode_dir = prepare_asset_write(project, episode_dir)
    return unwrap_service_result(update_fields(project, episode_dir, aid, values, gateway=asset_plan_gateway()))


def apply_asset_plan_gate_choice(project, key, choice, episode_dir=''):
    from domain.asset_plan import apply_gate_choice
    episode_dir = prepare_asset_write(project, episode_dir)
    return unwrap_service_result(apply_gate_choice(project, key, choice, episode_dir, gateway=asset_plan_gateway()))


def plan_unattended_assets(project, base, sources, scope='adopted'):
    """L3 为无人值守资产计划装配唯一的发布网关。"""
    from asset_batch_service import unattended_plan
    base = prepare_asset_write(project, base)
    return unattended_plan(project, base, sources, scope, gateway=asset_plan_gateway(),
                           context=project_context(project))


def note_asset_resume_round(project, ids, limit=None, now=None):
    from domain.asset_resume import note_round
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


def asset_detail_gateway():
    """L3 为资产详情图片绑定注入唯一的回滚发布器。"""
    return asset_plan_gateway()


def bind_asset_canonical_view(project, episode_dir, aid, view, source):
    """L3 编排资产详情正典板绑定。"""
    from domain.asset_detail_service import bind_canonical_view
    episode_dir = prepare_asset_write(project, episode_dir)
    result = bind_canonical_view(project, episode_dir, aid, view, source,
                                gateway=asset_detail_gateway(), context=project_context(project))
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def bind_asset_variant_thumbnail(project, episode_dir, aid, state_id, source):
    """L3 编排资产详情状态变体缩略图绑定。"""
    from domain.asset_detail_service import bind_variant_thumbnail
    episode_dir = prepare_asset_write(project, episode_dir)
    result = bind_variant_thumbnail(project, episode_dir, aid, state_id, source,
                                   gateway=asset_detail_gateway(), context=project_context(project))
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def pending_generated_assets(project, base):
    """L3 统一装配自动导入生成资产时的项目上下文。"""
    from domain.asset_generated_import_service import pending_generated
    return pending_generated(project, base, context=project_context(project))


def import_pending_generated_assets(project, base, report=None):
    """L3 装配生成资产导入所需的上下文与发布网关。"""
    from domain.asset_generated_import_service import import_pending_generated
    base = prepare_asset_write(project, base)
    return import_pending_generated(project, base, report, gateway=asset_batch_gateway(),
                                    context=project_context(project))


def unwrap_service_result(result):
    """L3 解包 L2 服务结果；L4 只接收既有业务数据或可展示异常。"""
    # 旧桌面测试桩仍返回裸值；正式写服务总是返回 ServiceResult。
    if not hasattr(result, 'ok'):
        return result
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def _json_gateway(**extra):
    """各 ``*_gateway()`` 的共同底座：唯一的 JSON 原子发布器；个别网关只补自己多出的能力。"""
    from agent.core import save
    return {'publish_json': save, **extra}
