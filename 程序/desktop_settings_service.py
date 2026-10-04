"""Atomic persistence for desktop-wide, non-project preferences."""
from pathlib import Path
import logging
from service_contract import SystemError, UserError, success

LOGGER = logging.getLogger(__name__)

def publish_desktop_settings(settings_path, current, updates, *, publish=None):
    """Merge desktop preference changes without mutating the caller on failure."""
    if not isinstance(current, dict):
        return UserError('桌面设置必须为对象')
    if not isinstance(updates, dict) or not updates:
        return UserError('桌面设置更新必须为非空对象')
    if any(not isinstance(key, str) or not key for key in updates):
        return UserError('桌面设置键必须为非空文本')
    path = Path(settings_path)
    if path.name != 'desktop_settings.json':
        return UserError('桌面设置只能写入 desktop_settings.json')
    merged = {**current, **updates}
    if not callable(publish):
        raise TypeError('桌面设置发布需要 L3 注入发布器')
    try:
        publish(path, merged)
    except OSError:
        LOGGER.exception('桌面设置保存失败')
        return SystemError('桌面设置保存失败，请检查文件权限和磁盘空间后重试。')
    return success(merged)
