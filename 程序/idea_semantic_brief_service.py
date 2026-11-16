"""历史入口：实体已迁至 ``orchestrator.idea_semantic_brief_service``（T10 包化）。

``import idea_semantic_brief_service`` 返回 ``orchestrator.idea_semantic_brief_service`` 本体：私有名、模块级状态与
按扁平名打的 ``mock.patch`` 补丁面和包内路径完全一致；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
import sys as _sys
from orchestrator import idea_semantic_brief_service as _entity

_sys.modules[__name__] = _entity
