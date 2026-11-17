# -*- coding: utf-8 -*-
"""红绿 Diff 视图（L4）：difflib 行级差异 + Text 红删绿增 + 接受/拒绝。

只消费 ``ui_tokens``；接受/拒绝经 ``on_decision(action)`` 回调（复用 HITL DIFF 信封）。
"""
from __future__ import annotations

import difflib
from tkinter import ttk

from ui_tokens import COLORS, SPACING
from ui_widgets import PrimaryButton, SecondaryButton, TextArea

OP_EQUAL = 'equal'
OP_DELETE = 'delete'
OP_INSERT = 'insert'


def diff_lines(before, after):
    """返回 ``[(op, line)]``；op ∈ equal/delete/insert。行级 Myers（SequenceMatcher）。"""
    old = str(before or '').splitlines()
    new = str(after or '').splitlines()
    rows = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new).get_opcodes():
        if tag == OP_EQUAL:
            rows.extend((OP_EQUAL, line) for line in old[i1:i2])
        elif tag == OP_DELETE:
            rows.extend((OP_DELETE, line) for line in old[i1:i2])
        elif tag == OP_INSERT:
            rows.extend((OP_INSERT, line) for line in new[j1:j2])
        else:  # replace
            rows.extend((OP_DELETE, line) for line in old[i1:i2])
            rows.extend((OP_INSERT, line) for line in new[j1:j2])
    return rows


def build_diff_view(parent, before, after, on_decision, *, height=12):
    """红删绿增只读 Diff + 接受/拒绝按钮。返回 Frame。"""
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    box = TextArea(frame, height=height, wrap='word', highlightthickness=0)
    box.pack(fill='x')
    box.tag_configure(OP_DELETE, foreground=COLORS['danger'], background=COLORS['danger_subtle'])
    box.tag_configure(OP_INSERT, foreground=COLORS['success_text'], background=COLORS['success_subtle'])
    rows = diff_lines(before, after)
    for op, line in rows:
        prefix = '- ' if op == OP_DELETE else '+ ' if op == OP_INSERT else '  '
        box.insert('end', prefix + line + '\n', op if op != OP_EQUAL else '')
    box.configure(state='disabled')
    row = ttk.Frame(frame)
    row.pack(anchor='w', pady=SPACING['xs'])
    PrimaryButton(row, text='接受修改', command=lambda: on_decision('approve')).pack(
        side='left', padx=SPACING['xs'])
    SecondaryButton(row, text='拒绝', command=lambda: on_decision('reject')).pack(
        side='left', padx=SPACING['xs'])
    return frame
