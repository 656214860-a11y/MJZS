"""「运行状况」弹窗（L4）：只读展示 task_center_service 的快照。"""
from __future__ import annotations

import tkinter as tk

import diagnostic_capture
import task_center_service
from ui_widgets import BaseDialog, TextArea


def show(desktop):
    """由设置页按钮打开；数据来自桌面当前的后台任务生命周期与诊断记录。"""
    try:
        degradations = diagnostic_capture._state().get('degradations') or []
    except Exception:
        degradations = []
    data = task_center_service.snapshot(getattr(desktop, 'background_tasks', None), degradations)
    dialog = BaseDialog(desktop.win, '运行状况', geometry='640x520', minsize=(420, 320))
    text = TextArea(dialog.content, wrap='word', height=20)
    text.pack(fill='both', expand=True)
    text.insert('1.0', '\n'.join(task_center_service.format_lines(data)))
    text.set_readonly(True)
    dialog.add_action('关闭', dialog.close, primary=True)
    return dialog
