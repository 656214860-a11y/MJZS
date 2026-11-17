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

本轮（R3275）只落签名空壳与事件名常量占位。
"""
from __future__ import annotations

# 事件名常量占位：值即 pet_bus.CONTRACT 待登记的 kind，轮 4 定稿。
KEYFRAME_REPLACED = "keyframe.replaced"
VIDEO_GENERATED = "video.generated"
PAID_INVOKED = "paid.invoked"

_bus = None
_errors = None


def bind(bus, errors=None) -> None:
    """注入事件总线与订阅者错误桶；实现见任务书轮 4。"""
    raise NotImplementedError


def emit(kind: str, **fields) -> dict | None:
    """经 ``pet_bus.emit_safe`` 发一条旁路事件；失败返回 ``None`` 不抛。"""
    raise NotImplementedError
