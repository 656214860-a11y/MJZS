"""历史入口：实体已迁至 ``contract.script_brief``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.script_brief import (
    BRIEF_FIELDS,
    BRIEF_LABELS,
    BRIEF_OPTIONAL_FIELDS,
    BRIEF_PRODUCTION_LOCKS_FIELD,
    BRIEF_RECOMMENDED_FIELDS,
    BRIEF_REQUIRED_FIELDS,
    BRIEF_REQUIREMENT_LEVELS,
    RHYTHM_TEMPLATE_FIELD,
    RHYTHM_TEMPLATE_PATH,
    WORKFLOW_LOCK_SCHEMA,
    WORKFLOW_PROJECTION_KEY,
    brief_document,
    missing_brief_fields,
    normalize_brief,
    normalize_workflow_projection,
)
