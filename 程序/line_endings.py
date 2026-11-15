"""历史入口：实体已迁至 ``infra.line_endings``（T10 包化）。

``import line_endings`` 返回 ``infra.line_endings`` 本体：私有名、模块级状态与
按扁平名打的 ``mock.patch`` 补丁面和包内路径完全一致；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
import sys as _sys
from infra import line_endings as _entity

_sys.modules[__name__] = _entity
