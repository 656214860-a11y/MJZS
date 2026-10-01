"""Atomic persistence for desktop-wide, non-project preferences."""
from pathlib import Path

from agent.core import save


def publish_desktop_settings(settings_path, current, updates):
    """Merge desktop preference changes without mutating the caller on failure."""
    if not isinstance(current, dict):
        raise ValueError('桌面设置必须为对象')
    if not isinstance(updates, dict) or not updates:
        raise ValueError('桌面设置更新必须为非空对象')
    if any(not isinstance(key, str) or not key for key in updates):
        raise ValueError('桌面设置键必须为非空文本')
    path = Path(settings_path)
    if path.name != 'desktop_settings.json':
        raise ValueError('桌面设置只能写入 desktop_settings.json')
    merged = {**current, **updates}
    save(path, merged)
    return merged
