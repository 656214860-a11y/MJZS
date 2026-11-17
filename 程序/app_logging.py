"""历史入口：实体已迁至 ``infra.app_logging``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
import sys as _sys
from infra import app_logging as _entity
_sys.modules[__name__] = _entity
