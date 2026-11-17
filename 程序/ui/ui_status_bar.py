# -*- coding: utf-8 -*-
"""统一状态栏组件（R2985 P0）：左区常驻段 + 右区滚动消息 + 点击历史面板。

业务模块只往 ``StatusBus`` 发消息；本组件负责渲染、生命周期与历史。
视觉取值全部引用 ``ui_tokens``（design_tokens.md 代码化），不写魔法数字与内联色值。
"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from ui_tokens import CHAR_WIDTH, COLORS, FONTS, SPACING, TEXT_ROWS
from ui_widgets import EllipsisLabel
from ui.ui_status_bus import StatusBus

LEVEL_STYLE = {
    'info': {'bg': COLORS['background_primary'], 'fg': COLORS['text_primary']},
    'success': {'bg': COLORS['success_subtle'], 'fg': COLORS['success_text']},
    'warning': {'bg': COLORS['primary_subtle'], 'fg': COLORS['primary_pressed']},
    'error': {'bg': COLORS['danger_subtle'], 'fg': COLORS['danger_text']},
}

LEVEL_PREFIX = {'info': '·', 'success': '✓', 'warning': '!', 'error': '✕'}

SEGMENT_DEFAULT_WIDTH = 24


class StatusBar(ttk.Frame):
    """一条全局底栏。

    - ``set_segment(key, text, ...)``：左区常驻段（截断 + 悬停全文 + 可选点击命令）；
    - 消息经 ``StatusBus`` 发布：error/warning 常驻直到替换或处理，info/success 自动消失；
    - 点击右区消息展开最近 N 条历史（不另开窗口，Esc／失焦／关闭按钮收起）。
    """

    def __init__(self, master, bus, *, neutral='就绪', tick_ms=100):
        super().__init__(master)
        if not isinstance(bus, StatusBus):
            raise TypeError('StatusBar 需要一个 StatusBus 实例')
        self._bus = bus
        self._neutral = str(neutral)
        self._tick_ms = tick_ms
        self._dismiss_token = 0
        self._segments = {}
        self._popup = None
        self._pending_afters = {}
        self._destroyed = False
        self.bind('<Destroy>', self._on_destroy, add='+')
        self._build()
        self._unsub = bus.subscribe(self._on_event)
        self._show_neutral()
        self._after(self._tick_ms, self._tick)

    # ---- after 托管：销毁后不残留回调 ----
    def _after(self, ms, fn, *args):
        def _wrap(*_a):
            self._pending_afters.pop(after_id, None)
            if self._destroyed:
                return
            return fn(*_a)

        try:
            after_id = self.after(int(ms), _wrap, *args)
        except tk.TclError:
            return None
        self._pending_afters[after_id] = True
        return after_id

    # ---- 结构 ----
    def _build(self):
        self.left_zone = tk.Frame(self, bg=COLORS['background_primary'])
        self.left_zone.pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        self.message = EllipsisLabel(self, text='', style='Muted.TLabel')
        self.message.pack(side='right', fill='x', expand=True,
                          padx=(SPACING['sm'], SPACING['sm']))
        self.message.bind('<Button-1>', self._toggle_history)

    # ---- 左区常驻段 ----
    def set_segment(self, key, text, *, tooltip=None, command=None, width=None):
        """新增或更新一个左区常驻段；返回该段的 EllipsisLabel。"""
        text = str(text)
        if key in self._segments:
            sep, label = self._segments[key]
            label.set_text(text)
            label.configure(width=width or SEGMENT_DEFAULT_WIDTH)
            if tooltip is not None:
                label.tooltip.text = tooltip
            return label
        sep = None
        if self._segments:
            sep = tk.Label(self.left_zone, text='·', bg=COLORS['background_primary'],
                           fg=COLORS['text_muted'], font=FONTS['pet_hint'])
            sep.pack(side='left')
        label = EllipsisLabel(self.left_zone, text=text, style='Muted.TLabel')
        label.configure(width=width or SEGMENT_DEFAULT_WIDTH)
        label.pack(side='left')
        if tooltip is not None:
            label.tooltip.text = tooltip
        if command is not None:
            label.bind('<Button-1>', lambda _event: command())
        self._segments[key] = (sep, label)
        return label

    def clear_segment(self, key):
        entry = self._segments.pop(key, None)
        if entry is None:
            return
        sep, label = entry
        label.destroy()
        if sep is not None:
            sep.destroy()

    def _on_destroy(self, _event):
        """销毁时停掉全部 after：Tk 会删除已登记命令名，残留脚本会以 invalid command 报错。"""
        self._destroyed = True
        for after_id in list(self._pending_afters):
            self._pending_afters.pop(after_id, None)
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass

    # ---- 消息渲染 ----
    def _on_event(self, event):
        if self._destroyed:
            return
        kind, message, _previous = event
        if kind == 'current':
            self._dismiss_token += 1
            self._render_message(message)
            if message.ttl is not None:
                token = self._dismiss_token
                self._after(int(message.ttl), self._expire_check, token)
        elif kind == 'expired':
            self._dismiss_token += 1
            self._show_neutral()

    def _render_message(self, message):
        style = LEVEL_STYLE[message.level]
        self.message.configure(background=style['bg'], foreground=style['fg'])
        prefix = LEVEL_PREFIX[message.level]
        self.message.set_text(prefix + ' ' + message.text if prefix != '·' else message.text)

    def _show_neutral(self):
        self.message.configure(background=COLORS['background_primary'],
                               foreground=COLORS['text_primary'])
        self.message.set_text(self._neutral)

    def _expire_check(self, token):
        if token == self._dismiss_token and self._bus.current is not None:
            self._bus.expire_current()

    # ---- 心跳 ----
    def _tick(self):
        if self._destroyed:
            return
        self._bus.pump()
        self._after(self._tick_ms, self._tick)

    # ---- 历史面板 ----
    def _toggle_history(self, _event=None):
        if self._popup is not None and self._popup.winfo_exists():
            self._close_history()
        else:
            self._open_history()

    def _open_history(self):
        # 弹窗走统一组件 BaseDialog、正文走 TextArea（业务模块不得直接建 Toplevel/Text）。
        from ui_widgets import BaseDialog, TextArea
        popup = BaseDialog(self, '消息历史', modal=False, chrome=False,
                           on_close=self._on_history_closed)
        header = tk.Label(popup.content, text='消息历史', bg=COLORS['background_card'],
                          fg=COLORS['text_heading'], font=FONTS['body'])
        header.pack(anchor='w', padx=SPACING['sm'], pady=(SPACING['sm'], SPACING['none']))
        close = tk.Label(popup.content, text='×', bg=COLORS['background_card'],
                         fg=COLORS['text_muted'], font=FONTS['body'])
        close.place(relx=1.0, x=-SPACING['sm'] - 12, y=SPACING['xs'], anchor='ne')
        close.bind('<Button-1>', lambda _event: popup.close())
        text = TextArea(popup.content, width=CHAR_WIDTH['field_md'], height=TEXT_ROWS['lg'],
                        wrap='word', state='disabled')
        text.pack(fill='both', expand=True, padx=SPACING['xs'], pady=(SPACING['none'], SPACING['sm']))
        lines = []
        for msg in self._bus.history():
            stamp = time.strftime('%H:%M:%S', time.localtime(msg.at))
            lines.append('%s [%s] %s' % (stamp, msg.level, msg.text))
        if lines:
            text.configure(state='normal')
            text.insert('1.0', '\n'.join(lines))
            text.configure(state='disabled')
        popup.bind('<FocusOut>', lambda _event: popup.close())
        popup.update_idletasks()
        x = self.winfo_rootx() + self.winfo_width() - popup.winfo_reqwidth()
        y = self.winfo_rooty() - popup.winfo_reqheight()
        popup.geometry('+%d+%d' % (max(0, x), max(0, y)))
        popup.focus_set()
        self._popup = popup

    def _on_history_closed(self):
        self._popup = None

    def _close_history(self):
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.close()
        self._popup = None

    # ---- 生命周期 ----
    def shutdown(self):
        self._dismiss_token += 1
        for after_id in list(self._pending_afters):
            self._pending_afters.pop(after_id, None)
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        self._unsub()
        self._close_history()
