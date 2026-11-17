# -*- coding: utf-8 -*-
"""参数微调面板（L4）：温度/生图步数/画面比例。

返回 ``(Frame, state)``；``state['values']()`` 读当前参数，``on_change`` 在滑条/下拉变化时回调。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui_tokens import COLORS, SPACING
from ui_widgets import SelectBox

ASPECT_RATIOS = ('16:9', '9:16', '4:3', '1:1')
DEFAULT_VALUES = {'temperature': 0.7, 'steps': 20, 'aspect': '16:9'}


def _read(variables):
    temperature, steps, aspect = variables
    return {'temperature': round(float(temperature.get()), 2),
            'steps': int(round(float(steps.get()))),
            'aspect': str(aspect.get())}


def _scale_row(parent, label, variable, start, end, notify):
    box = ttk.Frame(parent)
    box.pack(fill='x', pady=SPACING['xs'])
    ttk.Label(box, text=str(label), foreground=COLORS['text_secondary']).pack(anchor='w')
    ttk.Scale(box, from_=start, to=end, variable=variable, command=notify).pack(fill='x')


def _combo_row(parent, label, variable, options, notify):
    box = ttk.Frame(parent)
    box.pack(fill='x', pady=SPACING['xs'])
    ttk.Label(box, text=str(label), foreground=COLORS['text_secondary']).pack(anchor='w')
    SelectBox(box, textvariable=variable, values=tuple(options),
              state='readonly').pack(fill='x')


def build_param_panel(parent, values=None, *, on_change=None):
    """温度(0–2)/步数(1–60)/比例下拉；返回 ``(Frame, state)``。"""
    current = dict(DEFAULT_VALUES, **dict(values or {}))
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    temperature = tk.DoubleVar(master=frame, value=float(current['temperature']))
    steps = tk.IntVar(master=frame, value=int(current['steps']))
    aspect = tk.StringVar(master=frame, value=str(current['aspect']))
    variables = (temperature, steps, aspect)

    def notify(*_args):
        if on_change is not None:
            on_change(_read(variables))

    _scale_row(frame, '温度（创意度）', temperature, 0.0, 2.0, notify)
    _scale_row(frame, '生图步数', steps, 1.0, 60.0, notify)
    _combo_row(frame, '画面比例', aspect, ASPECT_RATIOS, notify)
    state = {'temperature': temperature, 'steps': steps, 'aspect': aspect,
             'values': lambda: _read(variables)}
    return frame, state
