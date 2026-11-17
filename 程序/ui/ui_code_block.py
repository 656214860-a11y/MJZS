# -*- coding: utf-8 -*-
"""JSON/提示词代码高亮块（L4）：Text 高亮 + 折叠/展开 + 复制 + 应用提示词。

只消费 ``ui_tokens``；复制/应用经回调交给调用方。
"""
from __future__ import annotations

import re
from tkinter import ttk

from ui_tokens import COLORS, SPACING
from ui_widgets import SecondaryButton, TextArea

_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[-+]?\d+(?:\.\d+)?|true|false|null')


def highlight_tokens(text):
    """JSON 词法切分：返回 ``[(fragment, kind)]``，kind ∈ plain/string/number/keyword。"""
    value = str(text or '')
    rows = []
    last = 0
    for match in _TOKEN.finditer(value):
        if match.start() > last:
            rows.append((value[last:match.start()], 'plain'))
        token = match.group(0)
        if token.startswith('"'):
            kind = 'string'
        elif token in ('true', 'false', 'null'):
            kind = 'keyword'
        else:
            kind = 'number'
        rows.append((token, kind))
        last = match.end()
    if last < len(value):
        rows.append((value[last:], 'plain'))
    return rows


def build_code_block(parent, text, *, language='json', on_copy=None, on_apply=None, height=10):
    """代码/提示词高亮块：高亮正文 + 收起/展开 + 复制 + 应用。返回 Frame。"""
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    box = TextArea(frame, height=height, wrap='none', highlightthickness=0)
    box.pack(fill='x')
    box.tag_configure('string', foreground=COLORS['success_text'])
    box.tag_configure('number', foreground=COLORS['warning_text'])
    box.tag_configure('keyword', foreground=COLORS['primary'])
    for fragment, kind in highlight_tokens(text):
        box.insert('end', fragment, kind if kind != 'plain' else '')
    box.configure(state='disabled')
    state = {'expanded': True, 'height': height}
    row = ttk.Frame(frame)
    row.pack(anchor='w', pady=SPACING['xs'])

    def toggle():
        state['expanded'] = not state['expanded']
        box.configure(height=state['height'] if state['expanded'] else 1)
        toggle_button.configure(text='收起' if state['expanded'] else '展开')

    toggle_button = SecondaryButton(row, text='收起', command=toggle)
    toggle_button.pack(side='left', padx=SPACING['xs'])
    if on_copy is not None:
        SecondaryButton(row, text='复制', command=lambda: on_copy(text)).pack(
            side='left', padx=SPACING['xs'])
    if on_apply is not None:
        SecondaryButton(row, text='应用此提示词', command=lambda: on_apply(text)).pack(
            side='left', padx=SPACING['xs'])
    return frame
