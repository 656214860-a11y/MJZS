# -*- coding: utf-8 -*-
"""HITL 卡片的 Tk 渲染（L4）：审批门三按钮 + 选择卡。

只消费 ``ui_tokens``；按钮走 ``ui_widgets`` 语义组件；决策经 ``on_decision(decision)``
回调交给调用方（不 import Desktop）。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from domain import hitl
from ui_tokens import COLORS, SPACING
from ui_widgets import PrimaryButton, SecondaryButton


def _frame(parent, title):
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    ttk.Label(frame, text=str(title or ''), foreground=COLORS['text_primary']).pack(anchor='w')
    return frame


def build_approval_gate(parent, request, on_decision):
    """审批门：确认采用／拒绝／重新生成 三按钮；点击回调 ``on_decision``。返回 Frame。"""
    title = str((request.get('payload') or {}).get('title') or '请确认')
    frame = _frame(parent, title)
    row = ttk.Frame(frame)
    row.pack(anchor='w', pady=SPACING['xs'])
    PrimaryButton(row, text='确认采用',
                  command=lambda: on_decision(hitl.decide(hitl.Decision.APPROVE))).pack(
        side='left', padx=SPACING['xs'])
    SecondaryButton(row, text='拒绝',
                    command=lambda: on_decision(hitl.decide(hitl.Decision.REJECT))).pack(
        side='left', padx=SPACING['xs'])
    SecondaryButton(row, text='重新生成',
                    command=lambda: on_decision(hitl.decide(hitl.Decision.REGENERATE))).pack(
        side='left', padx=SPACING['xs'])
    return frame


def _candidate_label(item):
    if isinstance(item, dict):
        return str(item.get('label') or item.get('title') or item.get('name') or item)
    return str(item)


def build_choice_card(parent, request, on_decision):
    """选择卡：候选单选 + 确认；选中值随 ``EDIT`` 决策回填 ``payload.selected``。返回 Frame。"""
    payload = request.get('payload') or {}
    frame = _frame(parent, str(payload.get('title') or '请选择'))
    candidates = list(payload.get('candidates') or ())
    selected = tk.StringVar(master=frame, value='')
    box = ttk.Frame(frame)
    box.pack(anchor='w', pady=SPACING['xs'])
    for index, item in enumerate(candidates):
        ttk.Radiobutton(box, text=_candidate_label(item), value=str(index),
                        variable=selected).pack(anchor='w')

    def confirm():
        value = selected.get()
        if value == '' or not candidates:
            return
        on_decision(hitl.decide(hitl.Decision.EDIT, {'selected': candidates[int(value)]}))

    PrimaryButton(frame, text='确认', command=confirm).pack(anchor='w', pady=SPACING['xs'])
    return frame
