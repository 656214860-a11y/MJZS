"""Tk 用例的共用样板：建根窗口（无显示时跳过）与按时长泵事件。"""
import time
import tkinter as tk
import unittest

from skip_reasons import PLATFORM_TK_DISPLAY


def make_root():
    """建一个 Tk 根窗口；本机没有可用显示时抛 SkipTest（跳过原因取登记常量）。"""
    try:
        return tk.Tk()
    except tk.TclError as exc:
        raise unittest.SkipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))


def pump(window, seconds=.3, idle_first=True):
    """持续处理 Tk 事件至少 seconds 秒。"""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if idle_first:
            window.update_idletasks()
        window.update()
        time.sleep(.005)

def stage_context_menu(widget, **coordinates):
    """走真实右键绑定，仅截获最后的弹出显示，供调用菜单项。"""
    from unittest.mock import patch
    from ui_widgets import ContextMenu
    with patch.object(ContextMenu, 'popup', autospec=True) as popup:
        widget.event_generate('<Button-3>', **coordinates)
    popup.assert_called_once()
    return popup.call_args.args[0]
