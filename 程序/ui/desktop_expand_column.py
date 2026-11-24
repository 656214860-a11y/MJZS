# -*- coding: utf-8 -*-
"""REQ-UI-SIDEBAR-1：可复用「点击展开一列隐藏图标」部件。

抽取自 ``desktop_files_panel_filters._build_stage_rail`` 的右缘图标列：
竖排 RailIcon 图标钮＋ScrollForm 滚动＋按内容钉宽。侧栏项目二级列、
资产管理二级入口与右侧文件图标列共用本类，不复制实现。

用法::

    column = ExpandIconColumn(parent, win, scrollbar=False, hug_height=True)
    column.add('assets', 'assets_files', '📁', '资产', command)
    column.finalize()
    column.frame.pack(...)          # 何时显隐由调用方决定

``frame=`` 可收养既有停靠框（右侧文件面板的 ``stage_rail``），
此时图标直接铺进该框，与抽取前的结构一致。
"""

import tkinter as tk
from tkinter import ttk

from responsive_ui import ScrollForm
from ui.ui_icons import IconLoader
from ui_tokens import COLORS, SPACING
from ui_widgets import SecondaryButton, Tooltip


class ExpandIconColumn:
    """一列隐藏图标：RailIcon 钮、可选滚动、按内容钉宽/钉高。

    ``keys=True`` 时给每颗钮 ``takefocus`` 并绑上下方向键与 Enter，
    Esc 由宿主（侧栏宿主绑定或浮层既有绑定）收起，不在本类重复处理。
    """

    def __init__(self, parent, win, *, bg=None, scrollbar=True,
                 hug_height=False, keys=False, frame=None):
        self.win = win
        self.frame = frame if frame is not None else ttk.Frame(parent)
        self._bg = bg if bg is not None else COLORS['background_primary']
        self._scrollbar = scrollbar
        self._hug_height = hug_height
        self._keys = keys
        self._scroller = None
        self.form = None
        self.buttons = {}
        self._items = []
        self._pinned = []

    @property
    def scroller(self):
        """ScrollForm 实例；首个非 pinned 图标加入后才创建。"""
        return self._scroller

    def _ensure_scroller(self):
        if self._scroller is None:
            self._scroller = ScrollForm(self.frame, bg=self._bg,
                                        scrollbar=self._scrollbar)
            self.form = self._scroller.form
        return self._scroller

    def icon_button(self, parent, icon_name, glyph, tip, command, *,
                    label=None):
        """与 ``_make_rail_icon_button`` 同构：PNG 在用图、缺图退文字、记 _rail_icon_name。"""
        image = IconLoader.nav_icon(self.win, icon_name) if icon_name else None
        text = label or glyph
        if image is not None:
            button = SecondaryButton(
                parent, text=text, image=image, compound='image', width=0,
                style='RailIcon.TButton', command=command)
        else:
            button = SecondaryButton(
                parent, text=text, width=0, style='RailIcon.TButton',
                command=command)
        button._rail_icon_name = icon_name
        if self._keys:
            button.configure(takefocus=1)
        Tooltip(button, tip)
        return button

    def add(self, key, icon_name, glyph, tip, command, *, label=None,
            pinned=False):
        """登记一颗图标；``pinned`` 钉在滚动区上方（如设置钮），其余进滚动表单。"""
        if pinned:
            button = self.icon_button(self.frame, icon_name, glyph, tip,
                                      command, label=label)
            button.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
            self._pinned.append(button)
        else:
            self._ensure_scroller()
            button = self.icon_button(self.form, icon_name, glyph, tip,
                                      command, label=label)
            button.pack(side='top', pady=(SPACING['none'], SPACING['xs']))
        self.buttons[key] = button
        self._items.append(button)
        return button

    def _bind_keys(self):
        order = list(self._items)

        def focus(index):
            target = order[index % len(order)]
            try:
                target.focus_set()
            except tk.TclError:
                pass

        for index, button in enumerate(order):
            button.bind('<Up>', lambda _e, i=index: focus(i - 1), add='+')
            button.bind('<Down>', lambda _e, i=index: focus(i + 1), add='+')
            button.bind('<Return>', lambda _e, b=button: b.invoke(), add='+')

    def finalize(self):
        """滚轮、键盘、按内容钉宽（hug_height 时连高度一起钉）。必须在 add 之后调用。"""
        scroller = self._ensure_scroller()
        scroller.bind_wheel()
        if self._keys:
            self._bind_keys()
        content_w = max((b.winfo_reqwidth() for b in self._items), default=0)
        if content_w:
            scroll_w = (scroller.scroll.winfo_reqwidth()
                        if scroller.scroll is not None else 0)
            self.frame.configure(width=content_w + scroll_w)
            self.frame.pack_propagate(False)
            scroller.canvas.configure(width=content_w)
        if self._hug_height:
            pinned_h = sum(b.winfo_reqheight() for b in self._pinned)
            scroll_h = sum(b.winfo_reqheight() for b in self._items
                           if b not in self._pinned)
            count = max(1, len(self._items))
            self.frame.configure(
                height=pinned_h + scroll_h + count * SPACING['xs'])
