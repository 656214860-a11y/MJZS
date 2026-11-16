"""无 Tk 的桌面换页决策与 after 计时器登记表（R1983 J4）。

从 ``desktop.Desktop`` 原样切出：侧栏导航的视频模式、整页缓存的失效判据与缓存项、换页前的闸门判定，
以及关闭窗口时要逐个取消的 after 任务名单。本模块不持有 Tk 控件、不写项目数据；页序号表
``page``（``pet_state.PAGE_OF``）与取消回调、存在性探测都由 L4 调用方注入。
"""
from __future__ import annotations

from typing import NamedTuple

# 关闭窗口时要取消的 after 任务属性，按原 cancel_timers 的先后顺序分两组：
# 第一组在各生命周期登记器取消之前，第二组在 ``_fit_job`` 之后。
NAV_TIMER_JOBS = ('_navigation_job', '_sidebar_fit_job')
STARTUP_TIMER_JOBS = ('_startup_tick_resume_id', '_startup_project_page_job', '_startup_script_build_job',
                      '_startup_project_recovery_job', '_legacy_project_migration_poll_id',
                      '_async_result_poll_id', '_auto_edit_result_poll_id', '_auto_handoff_result_poll_id')
# 窗口自己的后台任务生命周期登记器；最小 Desktop 替身可能没有，取不到就跳过。
LIFECYCLES = ('background_tasks', 'cloud_monitor_tasks')
# 八条自动流程的登记器挂在 ``owner.auto``（AutoState）上，顺序同原 ``auto_*_tasks`` 名单。
AUTO_LIFECYCLES = ('asset_tasks', 'keyframe_tasks', 'video_tasks', 'edit_tasks', 'handoff_tasks', 'previs_tasks')


def cancel_jobs(owner, names, after_cancel, tolerated):
    """逐个取消 ``owner`` 上登记的 after 任务并把属性置空；``tolerated`` 是取消时可忽略的异常（TclError）。"""
    for name in names:
        job = getattr(owner, name, None)
        setattr(owner, name, None)
        if job is not None:
            try:
                after_cancel(job)
            except tolerated:
                pass


def cancel_lifecycles(owner):
    """取消窗口拥有的各后台任务登记器；关闭路径必须兼容尚未初始化完的窗口。"""
    auto = getattr(owner, 'auto', None)
    registers = [getattr(owner, name, None) for name in LIFECYCLES]
    registers += [getattr(auto, name, None) for name in AUTO_LIFECYCLES]
    for lifecycle in registers:
        if lifecycle is not None:
            lifecycle.cancel()


def sidebar_video_mode(index, page, picked):
    """侧栏点「视频生成」：本次启动还没选过生成方式就先摆「选择生成方式」，其余页不带模式。"""
    return 'choose' if (index == page['video'] and not picked) else None


def next_video_mode(video_mode, picked, last_mode):
    """进视频页时的生成方式：返回 (模式, 是否已选过, 是否要把模式写回偏好)。

    ``video_mode`` 为 'choose' 表示回到选择页；传了具体模式就用它；都没有时只在本次启动选过的前提下
    沿用偏好里上次的模式。
    """
    if video_mode == 'choose':
        mode, picked = None, False
    elif video_mode:
        mode = video_mode
    else:
        mode = last_mode if picked else None
    save = False
    if mode in ('cloud', 'local'):
        picked = True
        save = last_mode != mode
    return mode, picked, save


def choosing_video(index, page, video_mode):
    """视频页还没选定生成方式（不需要分镜的那一屏）。"""
    return index == page['video'] and video_mode not in ('local', 'cloud')


def needs_adopted_storyboard(index, page, choosing, adopted):
    """首帧／白模预演／已选方式的视频页要求至少采用一份分镜：``adopted()`` 返回空列表即被拦下。

    ``adopted`` 是读偏好的回调，只在这几页才调用，别的页不碰磁盘。
    """
    gated = index in (page['keyframe'], page['previs']) or (index == page['video'] and not choosing)
    return gated and adopted() == []


def needs_source_selector(index, page, choosing, asset_subroute):
    """05–11 页顶部要摆分镜来源选择；视频选择屏和资产子路由（详情／清单）不摆。"""
    return (page['assets'] <= index <= page['audio'] and not choosing
            and not (index == page['assets'] and asset_subroute))


def stale_cache_keys(cache, index, page, *, root, rebuild, alive, signature=None):
    """整页缓存里该作废的键：换项目、内容框已销毁、02 页分镜签名变了，或目标页本身要重建。

    ``rebuild`` 为真表示目标页本身要重建（同页刷新，或不是从侧栏点回来）。
    ``alive(entry)`` 探测缓存项的内容框是否还在；``signature(root)`` 只在命中 02 页且前面几条都没作废时
    才计算（保持原来的惰性）。
    """
    stale_keys = []
    for key, entry in cache.items():
        stale = entry['root'] != root or not alive(entry)
        if not stale and key == index == page['script_structure'] and signature is not None:
            stale = entry.get('signature') != signature(root)
        if stale or (key == index and rebuild):
            stale_keys.append(key)
    return stale_keys


def cache_entry(holder, root, status_text, project_text):
    """缓存项：内容框、所属项目，以及离开时底栏上的那句话（等于项目路径的不留）。

    R2942：页面级「阶段配置」按钮已删，缓存不再存 stage_button。
    """
    return {'holder': holder, 'root': root,
            'note': '' if status_text == project_text else status_text}


class PagePlan(NamedTuple):
    """一次换页的完整决策。``route``：locked／free／home／blocked／startup_shell／roster／detail／builder。"""
    route: str
    reason: str = ''
    selector: bool = False
    align: bool = False
    cached: bool = False
    choosing: bool = False


def decide(index, page, snap, *, free_pages, cached_pages):
    """状态快照 → 换页决策；Tk 侧只按 ``route`` 摆控件，不再自己串判定。

    ``snap`` 键：lock_reason（该页被锁的原因，空为未锁）、has_root、video_mode、adopted（读已采用分镜的回调，
    只在需要闸门的页才调用）、asset_detail、asset_roster、loading_project。判定顺序与原 ``show`` 一致。
    """
    if snap['lock_reason']:
        return PagePlan('locked', reason=snap['lock_reason'])
    if index in free_pages:
        return PagePlan('free')
    if not snap['has_root']:
        return PagePlan('home')
    choosing = choosing_video(index, page, snap['video_mode'])
    if needs_adopted_storyboard(index, page, choosing, snap['adopted']):
        return PagePlan('blocked', choosing=choosing)
    roster, detail = bool(snap['asset_roster']), bool(snap['asset_detail'])
    selector = needs_source_selector(index, page, choosing, detail or roster)
    align = index in (page['edit'], page['delivery'])
    if index == page['script'] and snap['loading_project']:
        route = 'startup_shell'
    elif index == page['assets'] and roster:
        route = 'roster'
    elif index == page['assets'] and detail:
        route = 'detail'
    else:
        route = 'builder'
    return PagePlan(route, selector=selector, align=align, choosing=choosing,
                    cached=route == 'builder' and index in cached_pages)
