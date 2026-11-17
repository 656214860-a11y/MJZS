# -*- coding: utf-8 -*-
"""长任务进度卡（L4）：Canvas 进度条 + 转后台运行 + 完成回调。

页面不构造 ``ttk.Progressbar``（忙碌态边界要求）；进度条用 Canvas 自绘。
完成通知由调用方接 ``notifier``，本模块只做卡片与进度推进。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui_tokens import COLORS, SPACING
from ui_widgets import SecondaryButton

BAR_WIDTH = 240
BAR_HEIGHT = 10


def _paint(canvas, ratio, width=BAR_WIDTH, height=BAR_HEIGHT):
    """在 Canvas 上画一条进度条（底色 + 已完成段）。"""
    canvas.delete('all')
    canvas.create_rectangle(0, 0, width, height, fill=COLORS['surface_hover'], outline='')
    filled = int(width * max(0.0, min(1.0, float(ratio))))
    if filled > 0:
        canvas.create_rectangle(0, 0, filled, height, fill=COLORS['primary'], outline='')
    return canvas


def build_task_progress(parent, *, title='批量生成', total=10,
                        on_background=None, on_finish=None):
    """进度卡：标题 + Canvas 进度条 + 百分比 + 转后台；返回 ``(Frame, update(progress))``。"""
    total = max(1, int(total))
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    ttk.Label(frame, text=str(title), foreground=COLORS['text_primary']).pack(anchor='w')
    canvas = tk.Canvas(frame, width=BAR_WIDTH, height=BAR_HEIGHT, highlightthickness=0,
                       bg=COLORS['background_card'])
    canvas.pack(anchor='w', pady=SPACING['xs'])
    _paint(canvas, 0.0)
    percent = ttk.Label(frame, text='0%', foreground=COLORS['text_secondary'])
    percent.pack(anchor='w')
    row = ttk.Frame(frame)
    row.pack(anchor='w', pady=SPACING['xs'])
    if on_background is not None:
        SecondaryButton(row, text='转后台运行', command=on_background).pack(
            side='left', padx=SPACING['xs'])

    def update(progress):
        value = max(0, min(total, int(progress)))
        _paint(canvas, value / total)
        percent.configure(text='%d%%' % (100 * value // total))
        if value >= total and on_finish is not None:
            on_finish()
        return value

    return frame, update
