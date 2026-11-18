"""Atomic persistence for desktop-wide, non-project preferences."""
from pathlib import Path
import logging
from contract.service_contract import SystemError, UserError, success

LOGGER = logging.getLogger('desktop_settings_service')

def load_desktop_settings(settings_path, defaults, *, read, preserve=None):
    """启动时读取桌面设置；文件被手改或半写时不挡启动，先留一份副本再回落默认值。

    保存设置会整文件覆盖，直接回落会把用户改坏的内容丢掉，所以先复制成
    ``desktop_settings.json.corrupt`` 供找回。``read`` 与 ``preserve(path)`` 由调用方注入
    （L2 不直接写正式路径；不给 ``preserve`` 就不留副本）。
    """
    path = Path(settings_path)
    if not path.exists():
        return dict(defaults)
    try:
        value = read(path)
        if not isinstance(value, dict):
            raise ValueError('桌面设置必须为对象')
        return value
    except (OSError, ValueError):
        LOGGER.exception('桌面设置读取失败，已回落默认值')
        if preserve is not None:
            try:
                preserve(path)
            except OSError:
                LOGGER.warning('桌面设置副本保存失败')
        return dict(defaults)


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


def startup_settings(app, *, safe_start, defaults, read, preserve=None):
    """启动时取桌面设置（轮 3B D3-k 崩溃预算安全启动）。

    ``safe_start`` 为真（启动器二选一的「是」）时：设置按 ``defaults`` 内存值运行，
    ``settings_file`` 改指 ``程序/data/desktop_settings.json`` 影子文件——后续
    ``publish_desktop_settings`` 的名字校验照常通过，写入落在影子文件，用户
    ``desktop_settings.json`` 只读不覆盖。默认值里没有 ``project_choice_*``，
    ``daily_project_choice`` 自然返回 None → 不恢复上次项目。
    """
    app = Path(app)
    if safe_start:
        shadow = app / 'data' / 'desktop_settings.json'
        try:
            shadow.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            LOGGER.warning('安全启动影子目录创建失败，设置写入可能不可用')
        return shadow, dict(defaults)
    path = app / 'desktop_settings.json'
    return path, load_desktop_settings(path, defaults, read=read, preserve=preserve)
