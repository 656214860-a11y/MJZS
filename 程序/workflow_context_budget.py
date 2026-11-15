"""历史入口：实体已迁至 ``contract.workflow_context_budget``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.workflow_context_budget import (
    CHAR_NOTE,
    DEFAULT_OUTPUT_RESERVE_TOKENS,
    REQUEST_CONTEXT_MAX_CHARS,
    SECTION_LABELS,
    USAGE_NOTE,
    budget_advice,
    budget_sections,
    budget_split_options,
    compact_repeated_context,
    context_budget_error,
    context_budget_report,
    default_safety_margin,
    dominant_sections,
    ensure_request_context,
    estimate_tokens,
    hashlib,
    prepare_request_context,
    skill_inline_token_budget,
    text_fingerprint,
)
