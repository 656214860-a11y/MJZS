"""历史入口：实体已迁至 ``contract.shot_batches``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.shot_batches import (
    BATCH_ID,
    BATCH_MAX_SHOTS,
    BATCH_SECONDS,
    BATCH_SECONDS_LONG,
    BATCH_SHOTS,
    COMPLEX_SECONDS,
    DEFAULT_EXCLUDE,
    DEFAULT_RESPONSIBILITY,
    DEFAULT_SECONDS,
    EPISODE_BATCHES,
    EPISODE_SHOTS,
    EPISODE_TOTAL_BATCHES,
    REF_LABEL,
    SHOT_FIELDS,
    SHOT_SECONDS,
    TRIPLET,
    advise,
    assign,
    batches,
    check_batches,
    duration,
    group,
    normalize,
    number,
    pseudocode,
    re,
    rules_rows,
    schema,
    triplet,
    validate,
)
