"""历史入口：实体已迁至 ``contract.stage_path_service``（T10 包化）。

测试与未改写的消费方仍按扁平名导入；生产侧一律用包路径。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.stage_path_service import (
    LEGACY_NUMBERED,
    LEGACY_READ_UNTIL,
    Path,
    date,
    existing_dir,
    legacy_read_dirs,
    read_dirs,
    read_file,
    shared_reference_dir,
    shared_reference_read_dirs,
    stage_layout,
    write_dir,
)
