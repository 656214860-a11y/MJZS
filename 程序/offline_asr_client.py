"""历史入口：实体已迁至 ``domain.offline_asr_client``。

``import offline_asr_client`` 返回 ``domain.offline_asr_client`` 本体：私有名、模块级状态与
按扁平名打的 ``mock.patch`` 补丁面和包内路径完全一致；生产侧一律用包路径。
"""
import sys as _sys
from domain import offline_asr_client as _entity

_sys.modules[__name__] = _entity
