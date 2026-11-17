# -*- coding: utf-8 -*-
"""资产悬浮卡（L4）：正文里的资产名高亮 + 悬浮显示正典图/属性。

资产名按最长优先匹配并加下划线；悬停经 ``BaseDialog`` 弹非模态卡（``asset_thumbs``
取正典图），鼠标离开即关。回调由调用方按需注入。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import asset_thumbs
from ui_tokens import COLORS, SPACING
from ui_widgets import BaseDialog


def _card_key(parent):
    return getattr(parent, '_asset_hovercard', None)


def show_asset_hovercard(parent, asset):
    """在父控件上弹一张非模态资产卡；返回窗口。"""
    hide_asset_hovercard(parent)
    name = str((asset or {}).get('name') or '资产')
    window = BaseDialog(parent, name, modal=False, chrome=False)
    photo = asset_thumbs.thumbnail(window.content, (asset or {}).get('canon') or (asset or {}).get('path') or '')
    if photo is not None:
        label = tk.Label(window.content, image=photo)
        label.image = photo
    else:
        label = tk.Label(window.content, text='无正典图')
    label.pack(padx=SPACING['sm'], pady=SPACING['sm'])
    for key, value in dict((asset or {}).get('fields') or {}).items():
        ttk.Label(window.content, text='%s：%s' % (key, value)).pack(anchor='w', padx=SPACING['sm'])
    try:
        parent._asset_hovercard = window
    except tk.TclError:
        pass
    return window


def hide_asset_hovercard(parent):
    """关掉父控件上挂着的资产卡（没有则什么都不做）。"""
    window = _card_key(parent)
    if window is None:
        return
    try:
        window.destroy()
    except tk.TclError:
        pass
    try:
        del parent._asset_hovercard
    except AttributeError:
        pass


def highlight_assets(box, name, text, assets, *, on_hover=None):
    """把文本里出现的资产名加下划线并绑定悬浮；返回命中数。``assets`` 是 ``{名称: 资产}``。"""
    value = str(text or '')
    names = sorted((asset for asset in (assets or {}) if asset), key=len, reverse=True)
    if not names:
        box.insert('end', value)
        return 0
    count = 0
    last = 0
    cursor = 0
    while cursor < len(value):
        hit = next((asset for asset in names if value.startswith(asset, cursor)), None)
        if hit is None:
            cursor += 1
            continue
        if cursor > last:
            box.insert('end', value[last:cursor])
        tag = '%s_asset_%d' % (name, count)
        box.insert('end', hit, tag)
        box.tag_configure(tag, foreground=COLORS['text_primary'], underline=True)
        box.tag_bind(tag, '<Enter>',
                     lambda event, a=assets[hit]: (show_asset_hovercard(box, a),
                                                   on_hover(a) if on_hover is not None else None))
        box.tag_bind(tag, '<Leave>', lambda event: hide_asset_hovercard(box))
        count += 1
        last = cursor + len(hit)
        cursor = last
    if last < len(value):
        box.insert('end', value[last:])
    return count
