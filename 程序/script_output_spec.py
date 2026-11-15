"""历史入口：实体已迁至 ``contract.script_output_spec``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.script_output_spec import (
    LOUDNESS_DEFAULTS,
    OUTPUT_SPEC_DEFAULTS,
    PREVIEW_FPS,
    PREVIEW_SHORT_EDGE,
    describe_output_spec,
    loudness_filter,
    output_filter,
    overlay_metrics,
    parse_ratio,
    parse_resolution,
    preview_spec,
    re,
    resolve_output_spec,
)
