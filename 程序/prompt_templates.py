"""历史入口：实体已迁至 ``contract.prompt_templates``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.prompt_templates import (
    ANCHOR_TODO,
    DEFAULT_CAMERA,
    DEFAULT_COMPOSITION,
    DEFAULT_EXCLUDE,
    DEFAULT_RESPONSIBILITY,
    IMAGE_TEMPLATE,
    ROLE_TEMPLATE,
    SCENE_TODO,
    VIDEO_TEMPLATE,
    common_lines,
    contract_lines,
    image_prompt,
    image_template,
    merged_anchor,
    role_line,
    role_lines,
    role_template,
    rows,
    scene_line,
    strip_appearance,
    video_prompt,
    video_template,
)
