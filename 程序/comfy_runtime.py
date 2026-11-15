"""Headless ComfyUI launch/readiness helpers shared by production services."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from contract.platform_tools import open_path


def executable(settings):
    choices = [settings.get('comfy_exe', ''),
               r'C:\Program Files\Comfy Desktop\Comfy Desktop.exe',
               str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/ComfyUI/ComfyUI.exe')]
    return next((Path(value) for value in choices if value and Path(value).is_file()), None)


def open_comfy(settings=None):
    if settings is None:
        settings_file = Path(__file__).with_name('desktop_settings.json')
        settings = {}
        if settings_file.is_file():
            try:
                value = json.loads(settings_file.read_text(encoding='utf-8-sig'))
                settings = value if isinstance(value, dict) else {}
            except (OSError, ValueError):
                pass
    exe = executable(settings)
    if exe is None:
        raise ValueError('未找到本地 ComfyUI 桌面程序，请在助手中点击“桌面打开 ComfyUI”选择程序')
    open_path(exe)
    return exe


def wait_comfy(url, report=None, timeout=90, cancelled=None):
    """Wait for ComfyUI outside Tk; an unattended worker may stop the wait."""
    from comfy_service import Comfy
    client = Comfy(url)
    deadline = time.monotonic() + timeout
    if report:
        report('已打开本地 ComfyUI，正在等待服务就绪…')
    while True:
        if cancelled and cancelled():
            raise ValueError('已取消等待本地 ComfyUI 就绪')
        try:
            client.request('/system_stats')
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise ValueError('本地 ComfyUI 未就绪，请检查桌面程序和保存的本机地址：' + url) from None
            time.sleep(1)
