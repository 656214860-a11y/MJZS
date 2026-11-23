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
from ui_widgets import HintLabel, LineInput, PrimaryButton, SecondaryButton


def _frame(parent, title):
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    # 既有登记 1 处手写色：标题保留 foreground，新增文案用 Muted.TLabel／HintLabel。
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


def build_choice_card(parent, request, on_decision, *, on_pick=None, selected=None):
    """选择卡：候选单选 + 确认；选中值随 ``EDIT`` 决策回填 ``payload.selected``。返回 Frame。

    传 ``on_pick`` 时改为「点选项即发出」：最多显示 ``MAX_CHOICES`` 个，超过时保留
    「其他…」输入；点选后所有按钮置灰并显示「已选：X」，同一张卡不再可点。传
    ``selected`` 用于重绘已选状态，卡片只读。
    """
    payload = request.get('payload') or {}
    if on_pick is not None:
        return _build_pick_card(parent, payload, on_decision, on_pick, selected)
    frame = _frame(parent, str(payload.get('title') or '请选择'))
    candidates = list(payload.get('candidates') or ())
    selected_var = tk.StringVar(master=frame, value='')
    box = ttk.Frame(frame)
    box.pack(anchor='w', pady=SPACING['xs'])
    for index, item in enumerate(candidates):
        ttk.Radiobutton(box, text=_candidate_label(item), value=str(index),
                        variable=selected_var).pack(anchor='w')

    def confirm():
        value = selected_var.get()
        if value == '' or not candidates:
            return
        on_decision(hitl.decide(hitl.Decision.EDIT, {'selected': candidates[int(value)]}))

    PrimaryButton(frame, text='确认', command=confirm).pack(anchor='w', pady=SPACING['xs'])
    return frame


def _build_pick_card(parent, payload, on_decision, on_pick, selected):
    """点选项即发出的选择卡；复用同一套 HITL 决策信封。"""
    frame = _frame(parent, str(payload.get('title') or '请选择'))
    candidates = list(payload.get('candidates') or ())
    shown = candidates[:hitl.MAX_CHOICES]
    truncated = bool(payload.get('truncated')) or len(candidates) > hitl.MAX_CHOICES
    buttons = []
    locked = [bool(str(selected or '').strip())]
    other_entry = other_send = None

    def lock(text):
        locked[0] = True
        for button in buttons:
            try: button.configure(state='disabled')
            except tk.TclError: pass
        if other_send is not None:
            try:
                other_send.configure(state='disabled')
                other_entry.configure(state='disabled')
            except (tk.TclError, AttributeError): pass
        status.configure(text='已选：' + str(text))

    def pick(item, label):
        if locked[0]:
            return
        value = dict(item) if isinstance(item, dict) else str(item)
        lock(label)
        on_decision(hitl.decide(hitl.Decision.EDIT, {'selected': value}))
        on_pick(str(label))

    row = ttk.Frame(frame)
    row.pack(anchor='w', pady=SPACING['xs'])
    for item in shown:
        label = _candidate_label(item)
        button = SecondaryButton(row, text=label, command=lambda i=item, t=label: pick(i, t))
        button.pack(side='left', padx=SPACING['xs'])
        buttons.append(button)
    if truncated:
        other = ttk.Frame(frame)
        other.pack(anchor='w', pady=SPACING['xs'])
        HintLabel(other, text='其他…').pack(side='left', padx=SPACING['xs'])
        other_entry = LineInput(other, placeholder='请输入')
        other_entry.pack(side='left', padx=SPACING['xs'])

        def send_other():
            value = str(other_entry.get() or '').strip()
            if value:
                pick(value, value)

        other_send = PrimaryButton(other, text='发送', command=send_other)
        other_send.pack(side='left', padx=SPACING['xs'])
    status = ttk.Label(frame, text='', style='Muted.TLabel')
    status.pack(anchor='w', pady=SPACING['xs'])
    if locked[0]:
        lock(str(selected))
    return frame
