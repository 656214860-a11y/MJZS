"""历史入口：实体已迁至 ``contract.production_model_contract``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.production_model_contract import (
    ASSET_CLOUD_MODELS,
    ASSET_LOCAL_MODEL,
    KEYFRAME_MODELS,
    LOCAL_KEYFRAME_MODEL,
    SEEDREAM_KEYFRAME_MODEL,
)
