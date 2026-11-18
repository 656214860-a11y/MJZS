# -*- coding: utf-8 -*-
"""幂等键：付费与写路径「同一件事只做一次」的唯一入口（L1 基础设施）。

14 个模块各自 ``import hashlib`` 手搓 sha256、口径互不相同（迁移清单只登记、
不在本轮迁移，见 L2 领域服务层优化任务书轮 2 结果文件），``recon_service``
这条付费路径原本完全没有防护。本模块收口幂等键的唯一算法：

- ``key_of(*parts)``：把业务要素逐个 ``str()``、以 ``\\x1f`` 分隔后取
  utf-8 字节的 sha256 十六进制串。哈希不重复实现——启动时
  ``infra.hash_backend.install()`` 已把 ``hashlib`` 固定到内置实现，
  本模块只 ``import hashlib`` 使用既有后端；结构化入参由调用方先规范化成
  字符串（如 ``json.dumps(..., sort_keys=True)``），保证「同一业务要素」
  得到同一键、键本身不泄漏原文。
- 落盘标记的读写与命中判定归各领域服务（本轮 ``recon_service``）：键只
  负责「同一件事」的指纹，不负责存储与状态机。
"""
from __future__ import annotations

import hashlib

_SEPARATOR = '\x1f'


def key_of(*parts: object) -> str:
    """把 ``parts`` 规范化拼接为幂等键（sha256 hex）。

    逐个 ``str()`` 后以 ``\\x1f`` 连接、utf-8 编码取 sha256；调用方负责把
    dict／list 等结构化入参先规范化成字符串，本函数不做 JSON 序列化。
    """
    payload = _SEPARATOR.join(str(part) for part in parts).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
