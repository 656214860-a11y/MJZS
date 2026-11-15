"""历史入口：实体已迁至 ``contract.prop_assets``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.prop_assets import (
    CHARACTER_RULES,
    RULES,
    copy,
    inline_text,
    normalize_shot,
    re,
    removed_ids,
    requires_asset,
)
