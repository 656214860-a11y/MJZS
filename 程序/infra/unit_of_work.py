# -*- coding: utf-8 -*-
"""事务原语：把「登记路径 → 写盘 → 失败恢复」收成 begin/commit/rollback 三件套（L1 基础设施）。

现状 ``domain/`` 里 7 处各写一遍「暂存→校验→替换→失败恢复」，其中 4 处回滚不完整，
且全部只在 ``except Exception`` 内生效——取消与进程中断不回滚。本模块将成为唯一实现：

- ``begin(paths)``：登记一组目标路径，记录每个路径的原内容摘要（原本不存在的路径
  记为「原本不存在」），返回事务令牌；此后调用方可自由写这些路径。
- ``commit(token)``：事务成功，丢弃全部备份与登记，令牌作废。
- ``rollback(token)``：逐个把登记路径恢复成 ``begin`` 时的内容（含「原本不存在」
  的删除语义），**不吞调用方正在处理的原异常**；恢复自身失败要如实抛出或记录，
  不静默 ``pass``。

令牌是不透明对象，调用方不得解读其内部结构。实现与 7 处接入分别在
L2 领域服务层优化任务书的轮 5／轮 6 落地；本轮（R3275）只落签名空壳。
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def begin(paths: Iterable[Path]) -> object:
    """登记 ``paths`` 的原内容摘要并返回事务令牌；实现见任务书轮 5。"""
    raise NotImplementedError


def commit(token: object) -> None:
    """提交事务：丢弃全部备份与登记，令牌作废；实现见任务书轮 5。"""
    raise NotImplementedError


def rollback(token: object) -> None:
    """回滚事务：逐个恢复原内容，不吞调用方原异常；实现见任务书轮 5。"""
    raise NotImplementedError
