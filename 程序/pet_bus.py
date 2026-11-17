"""历史入口：实体已迁至 ``contract.pet_bus``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.pet_bus import (
    Bus,
    CONTRACT,
    ERROR_LIMIT,
    ERROR_PERSIST_LIMIT,
    ErrorLog,
    HISTORY_LIMIT,
    LIVE_EVENTS,
    PENDING_LIMIT,
    Path,
    SEEN_LIMIT,
    SHEDDABLE_EVENTS,
    STAGES,
    STAGE_EVENTS,
    STAGE_NAMED,
    STAGE_NAMES,
    TERMINAL_EVENTS,
    emit_safe,
    event,
    hashlib,
    identify,
    is_sheddable,
    json,
    queue,
    read_json,
    stage_label,
    stage_name,
    stage_step,
    threading,
    time,
)
