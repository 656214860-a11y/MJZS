# -*- coding: utf-8 -*-
"""领域事件旁路：业务状态变化对上层的唯一提示通道（L2 领域服务）。

现状 L2 对上层完全不可见（``pet_bus.emit_safe`` 调用 0 处），上层只能靠轮询文件。
本模块薄封装 ``contract.pet_bus.emit_safe``：先 ``bind(bus, errors)`` 注入总线
与订阅者错误桶，此后 ``emit(kind, **fields)`` 发一条旁路事件，发送模式与
``infra.usage_snapshot`` 的 ``bind_bus``＋``emit_safe`` 一致。

硬边界（任务书 L2-D10）：**只做旁路提示，不作为状态唯一来源**——状态一致性
不押在广播可靠性上；总线未绑定或发送失败都只记一笔返回 ``None``，绝不影响主流程。
事件 ``kind`` 必须先登记进 ``pet_bus.CONTRACT`` 才能发出（``event()`` 会拒绝
未登记 kind），常量值与 CONTRACT 登记在任务书轮 4 同批落地。

R3291（任务书轮 4）落地实现：``bind``/``emit`` 与三个高频事件常量；生产侧
``bind`` 由 L3/UI 后续接入，未绑定时 ``emit`` 为安全 no-op。
"""
from __future__ import annotations

import infra.app_logging as app_logging

# 事件名常量：值即 pet_bus.CONTRACT 已登记的 kind。
KEYFRAME_REPLACED = "keyframe.replaced"
VIDEO_GENERATED = "video.generated"
PAID_INVOKED = "paid.invoked"

_bus = None
_errors = None


def bind(bus, errors=None) -> None:
    """注入事件总线与订阅者错误桶；与 ``infra.usage_snapshot.bind_bus`` 同模式。

    换项目重建总线后由调用方重新 bind；``bus=None`` 解除绑定，emit 回到 no-op。
    """
    global _bus, _errors
    _bus = bus
    _errors = errors if errors is not None else []


def emit(kind: str, **fields) -> dict | None:
    """经 ``pet_bus.emit_safe`` 发一条旁路事件；任何失败返回 ``None`` 不抛。

    ``emit_safe`` 已吞 ``bus.emit`` 异常，但 ``pet_bus.event()`` 的契约校验
    （kind 未登记／缺必填字段）与错误桶自身的意外仍可能抛出——这里再兜一层，
    只记 ``app_logging.swallowed()``，绝不向上抛（L2-D10 硬边界）。
    """
    if _bus is None:
        return None
    try:
        import contract.pet_bus as pet_bus
        return pet_bus.emit_safe(_bus, _errors, kind, **fields)
    except Exception:
        app_logging.swallowed('domain_events.emit')
        return None
