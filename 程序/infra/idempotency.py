# -*- coding: utf-8 -*-
"""幂等键：付费与写路径「同一件事只做一次」的唯一入口（L1 基础设施）。

现状 14 个模块各自 ``import hashlib`` 手搓 sha256、口径互不相同，
``recon_service`` 这条付费路径完全没有防护。本模块收口两件事：

- ``key_of(*parts)``：把业务要素规范化拼接后取 sha256 十六进制串，作为幂等键。
  哈希本身不重复实现——启动时 ``infra.hash_backend.install()`` 已把 ``hashlib``
  固定到内置实现，本模块只 ``import hashlib`` 使用既有后端。
- 轮 2 补 claim／complete 台账：同一 key 第二次进入直接判「已处理」，
  不再付费、不再写盘。

实现与 ``recon_service`` 接入在 L2 领域服务层优化任务书的轮 2 落地；
本轮（R3275）只落签名空壳。
"""
from __future__ import annotations


def key_of(*parts: object) -> str:
    """把 ``parts`` 规范化拼接为幂等键（sha256 hex）；实现见任务书轮 2。"""
    raise NotImplementedError
