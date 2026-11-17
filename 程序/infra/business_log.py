# -*- coding: utf-8 -*-
"""结构化业务日志：``log_event(kind, **fields)``（L1 基础设施）。

现状 ``domain/`` 里 38 条日志全部只有中文单参数、0 个业务字段，出了事只能靠猜。
本模块是唯一入口：调用方给事件类别与白名单字段，落一条带业务上下文的结构化记录，
字段至少覆盖 stage／shot_id／asset_id／cost_ms／outcome。

硬边界：**不得写入用户项目内容、密钥或绝对路径**——字段值只允许标识符、枚举、
计数与耗时；错误原文、提示词、文件名等自由文本一律不进 ``fields``。
``FIELDS`` 是允许出现在 ``fields`` 里的键集合，新增字段须先在这里登记。

实现与 8 个大模块接入在 L2 领域服务层优化任务书的轮 7 落地；本轮（R3275）
只落签名空壳。
"""
from __future__ import annotations

# fields 白名单：只允许这些键携带业务上下文，防止项目内容／密钥混进日志。
FIELDS = frozenset({"stage", "shot_id", "asset_id", "cost_ms", "outcome"})


def log_event(kind: str, **fields) -> None:
    """记录一条结构化业务事件；白名单外字段的处置与落盘格式见任务书轮 7。"""
    raise NotImplementedError
