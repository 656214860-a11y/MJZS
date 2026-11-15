"""历史入口：实体已迁至 ``contract.pet_settings_contract``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.pet_settings_contract import (
    LEVEL_NOTES,
    TABS,
)
