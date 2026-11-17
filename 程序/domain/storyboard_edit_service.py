"""Persistence boundary for user-edited storyboard JSON documents."""
import logging
from pathlib import Path

from contract.service_contract import SystemError, UserError, success

LOGGER = logging.getLogger('storyboard_edit_service')

def save_edited_json(path, data, publish=None):
    """Return a result carrying the saved path; the injected publisher is atomic."""
    if not callable(publish):
        raise TypeError('分镜编辑发布必须由 L3 注入。')
    try:
        target = Path(path).resolve()
        if target.suffix.lower() != '.json':
            return UserError('分镜编辑只能保存 JSON 文件')
        publish(target, data)
    except OSError:
        LOGGER.exception('分镜编辑保存失败')
        return SystemError('分镜保存失败，请检查文件权限和磁盘空间后重试。')
    return success(target)
