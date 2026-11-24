"""历史入口：实体已迁至 ``domain.video_staleness``（视频持久过期标记）。

``import video_staleness`` 返回 ``domain.video_staleness`` 本体：私有名、模块级状态与
按扁平名打的 ``mock.patch`` 补丁面和包内路径完全一致；生产侧一律用包路径。
"""
import sys as _sys
from domain import video_staleness as _entity

_sys.modules[__name__] = _entity
