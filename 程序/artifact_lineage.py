"""历史入口：实体已迁至 ``contract.artifact_lineage``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.artifact_lineage import (
    CURRENT,
    FILE_NAME,
    MISSING,
    PRIMARY_ROLE,
    Path,
    STALE,
    UNKNOWN,
    adopt,
    affected,
    check,
    datetime,
    file_hash,
    read_json,
    record,
    save,
    source_available,
    source_status,
)
