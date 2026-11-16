"""历史入口：实体已迁至 ``domain.voice_ai``。

``import voice_ai`` 返回 ``domain.voice_ai`` 本体：私有名、模块级状态与
按扁平名打的 ``mock.patch`` 补丁面和包内路径完全一致；生产侧一律用包路径。
"""
import sys as _sys
from domain import voice_ai as _entity

_sys.modules[__name__] = _entity
