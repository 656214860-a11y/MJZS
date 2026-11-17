"""用户可见项目文件名：只展示日期，同日重复用序号避免覆盖。"""
from datetime import datetime
from pathlib import Path


def dated_path(parent, prefix, suffix='', at=None):
    """返回 ``前缀_YYYYMMDD[_序号]`` 的未占用路径，不暴露时分秒。"""
    moment = datetime.fromtimestamp(at) if at is not None else datetime.now()
    base = str(prefix) + '_' + moment.strftime('%Y%m%d')
    parent = Path(parent)
    candidate = parent / (base + suffix)
    serial = 2
    while candidate.exists():
        candidate = parent / (base + '_' + str(serial) + suffix)
        serial += 1
    return candidate
