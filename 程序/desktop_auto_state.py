"""Desktop 无人值守流程的状态容器（L3，无 Tk）。

R1983 J1a（R1985 落地）：自动定稿／粗剪／首帧／资产／视频／预演／交接／采用八条流程原先把 62 个
``auto_*`` 属性直接挂在 ``Desktop`` 的 ``self`` 上，``desktop.py``、``desktop_auto_flows.py``、
``desktop_automation_tick.py`` 等多个类都在写。这里把它们收进一个状态对象，``Desktop.auto`` 持有；
三个主要调用方改为读写 ``self.auto.<字段>``。

- 字段名＝旧属性名去掉 ``auto_`` 前缀；六个代次计数 ``_auto_<流程>_ticket`` 对应 ``<流程>_ticket``。
- 旧属性名转发已在 R2017 退役：一律读写 ``self.auto.<字段>``；``AutoStateHolderMixin`` 只保留
  ``auto`` 缺失时的懒建默认状态。
- 只放状态，不放行为，也不持有 Tk 控件；队列与任务生命周期由 ``create_auto_state`` 按注入的工厂创建，
  所以本模块不反向导入 L4 的 ``pet_ui``。
"""
from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Any, Callable

from desktop_automation_service import BackgroundTaskLifecycle


@dataclass
class AutoState:
    """八条自动流程的运行状态。默认值与原 ``Desktop._initialize_automation_state`` 逐项一致。"""

    adopt_due: int = 0
    adopt_errors: dict = field(default_factory=dict)
    adopt_signature: Any = None
    adopt_pending: bool = False
    adopt_startup: bool = True

    final_due: int = 0
    final_busy: bool = False
    final_queue: Any = None
    final_signature: Any = None
    final_notice: Any = None
    final_blocked: bool = False
    final_error: str = ''

    edit_due: int = 0
    edit_ticket: int = 0
    edit_tasks: Any = None
    edit_busy: bool = False
    edit_queue: Any = None
    edit_signature: Any = None
    edit_error: str = ''

    keyframe_due: int = 0
    keyframe_ticket: int = 0
    keyframe_tasks: Any = None
    keyframe_busy: bool = False
    keyframe_queue: Any = None
    keyframe_messages: Any = field(default_factory=queue.Queue)
    keyframe_signature: Any = None
    keyframe_blocked: Any = None
    keyframe_error: str = ''

    asset_due: int = 0
    asset_ticket: int = 0
    asset_tasks: Any = None
    asset_busy: bool = False
    asset_queue: Any = None
    asset_messages: Any = field(default_factory=queue.Queue)
    asset_signature: Any = None
    asset_attempt: int = 0
    asset_blocked: Any = None
    asset_error: str = ''
    asset_tried: Any = None

    video_due: int = 0
    video_ticket: int = 0
    video_tasks: Any = None
    video_busy: bool = False
    video_queue: Any = None
    video_messages: Any = field(default_factory=queue.Queue)
    video_signature: Any = None
    video_notice: Any = None
    video_error: str = ''
    video_last: str = ''

    previs_due: int = 0
    previs_ticket: int = 0
    previs_tasks: Any = None
    previs_signature: Any = None
    previs_notice: Any = None
    previs_error: str = ''

    handoff_due: int = 0
    handoff_ticket: int = 0
    handoff_tasks: Any = None
    handoff_busy: bool = False
    handoff_queue: Any = None
    handoff_signature: Any = None
    handoff_error: str = ''


def create_auto_state(history_path, *, stage_queue: Callable, drain: Callable) -> AutoState:
    """按原初始化顺序建好队列与任务生命周期。

    ``stage_queue(阶段名[, sink])`` 由 L4 注入（``pet_ui.StageQueue``），``drain`` 是宠物的
    ``drain``；定稿／粗剪／视频／交接把队列取件结果报给它，首帧与资产不报。
    """
    def tasks():
        return BackgroundTaskLifecycle(history_path)

    return AutoState(
        final_queue=stage_queue('final', drain),
        edit_tasks=tasks(),
        edit_queue=stage_queue('edit', drain),
        keyframe_tasks=tasks(),
        keyframe_queue=stage_queue('keyframe'),
        asset_tasks=tasks(),
        asset_queue=stage_queue('assets'),
        video_tasks=tasks(),
        video_queue=stage_queue('video', drain),
        previs_tasks=tasks(),
        handoff_tasks=tasks(),
        handoff_queue=stage_queue('delivery', drain),
    )


def flow_slot(host, name):
    """流程名 → (持有者, 字段前缀)：``auto_<流程>`` 的状态落在 ``host.auto``，其余（``cloud_monitor``）仍在窗口上。"""
    if name.startswith('auto_'):
        return host.auto, name[len('auto_'):]
    return host, name


def flow_get(host, name, suffix, default=None):
    owner, prefix = flow_slot(host, name)
    return getattr(owner, prefix + suffix, default)


def flow_set(host, name, suffix, value):
    owner, prefix = flow_slot(host, name)
    setattr(owner, prefix + suffix, value)


class AutoStateHolderMixin:
    """``auto`` 缺失（测试里绕过 __init__ 的 Desktop.__new__）时首次访问补默认状态。"""

    def __getattr__(self, name):
        if name == 'auto':
            state = vars(self)['auto'] = AutoState()
            return state
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")
