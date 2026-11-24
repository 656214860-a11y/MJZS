# -*- coding: utf-8 -*-
"""统一状态栏组件（R2985 P0）：左区常驻段 + 右区滚动消息 + 点击历史面板。

业务模块只往 ``StatusBus`` 发消息；本组件负责渲染、生命周期与历史。
视觉取值全部引用 ``ui_tokens``（design_tokens.md 代码化），不写魔法数字与内联色值。
"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from ui_tokens import (CHAR_WIDTH, COLORS, FONTS, SPACING, STATUS_BAR_EDGE_PAD, STATUS_BAR_FONT,
                       STATUS_BAR_SEGMENT_MAX_WIDTH, STATUS_BAR_SEPARATOR, STATUS_BAR_SEPARATOR_GAP, TEXT_ROWS)
from ui_widgets import EllipsisLabel
from ui.ui_popup import char_unit_px, measure_text_width
from ui.ui_status_bus import StatusBus

LEVEL_STYLE = {
    'info': {'bg': COLORS['background_primary'], 'fg': COLORS['text_primary']},
    'success': {'bg': COLORS['success_subtle'], 'fg': COLORS['success_text']},
    'warning': {'bg': COLORS['primary_subtle'], 'fg': COLORS['primary_pressed']},
    'error': {'bg': COLORS['danger_subtle'], 'fg': COLORS['danger_text']},
}

LEVEL_PREFIX = {'info': '·', 'success': '✓', 'warning': '!', 'error': '✕'}

# 左区各段、分隔符和右区的中性提示共用这一档灰（ui_theme 里 Muted.TLabel 的字色就是 text_secondary）。
SEGMENT_STYLE = 'Muted.TLabel'
MUTED_TEXT = COLORS['text_secondary']


class SegmentLabel(EllipsisLabel):
    """左区的一段：文字不超过上限就按文字本身的宽度显示全文，超过才定在上限宽度、截断并在悬停时给全文。

    调用方显式给了 ``width``（字符数）的段维持那个宽度，照基类的办法截断。
    """

    def __init__(self, master, *, text='', width=None):
        self._natural = False
        self._fixed = None
        super().__init__(master, text='', style=SEGMENT_STYLE, font=STATUS_BAR_FONT)
        self.fit(text, width)

    def fit(self, text, width=None):
        self.full_text = str(text)
        self.tooltip.text = self.full_text
        self._fixed = int(width) if width else None
        if self._fixed:
            self._natural, units = False, self._fixed
        else:
            root = self.winfo_toplevel()
            cap = STATUS_BAR_SEGMENT_MAX_WIDTH * char_unit_px(STATUS_BAR_FONT, root)
            self._natural = measure_text_width(STATUS_BAR_FONT, [self.full_text], root=root) <= cap
            # ttk 的 width 为 0 即按文字本身的宽度
            units = 0 if self._natural else STATUS_BAR_SEGMENT_MAX_WIDTH
        self.configure(width=units)
        self._render()

    def set_text(self, text):
        self.fit(text, self._fixed)

    def _render(self, _event=None):
        if not self._natural:
            return super()._render(_event)
        if self.cget('text') != self.full_text:
            self.configure(text=self.full_text)


class StatusBar(ttk.Frame):
    """一条全局底栏。

    - ``set_segment(key, text, ...)``：左区常驻段（按文字定宽，超过上限才截断 + 悬停全文 + 可选点击命令）；
      文字为空的段不占位，看得见的段两两之间一个分隔符、两侧等距；
    - 别的模块直接摆进 ``left_zone`` 的控件（如用量指示）算一段，间距和分隔符由本栏统一给；
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
        self._order = []        # 左区的控件按登记先后排：各段的文字控件，和别的模块摆进来的控件
        self._separators = {}   # 控件 -> 排在它前面的分隔符（前面没有可见的段时不摆出来）
        self._guests = set()
        self._relayout_queued = False
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
        self.left_zone = ttk.Frame(self)
        self.left_zone.pack(side='left', padx=(STATUS_BAR_EDGE_PAD, SPACING['none']))
        self.left_zone.bind('<Configure>', self._queue_relayout, add='+')
        self.message = EllipsisLabel(self, text='', style=SEGMENT_STYLE, font=STATUS_BAR_FONT)
        self.message.pack(side='right', fill='x', expand=True,
                          padx=(STATUS_BAR_EDGE_PAD, STATUS_BAR_EDGE_PAD))

    # ---- 左区常驻段 ----
    def set_segment(self, key, text, *, tooltip=None, command=None, width=None):
        """新增或更新一个左区常驻段；返回该段的 EllipsisLabel。

        宽度按文字定，超过 ``STATUS_BAR_SEGMENT_MAX_WIDTH`` 才截断；给了 ``width`` 的段维持那个宽度。
        文字为空的段不占位，再有文字时回到它登记时的位置。
        """
        entry = self._segments.get(key)
        if entry is None:
            self._adopt_guests()  # 先认下已经摆进来的外来控件，新段排在它们后面
            label = SegmentLabel(self.left_zone, text=text, width=width)
            if command is not None:
                label.bind('<Button-1>', lambda _event: command())
            sep = self._separators[label] = self._new_separator()
            self._order.append(label)
            self._segments[key] = (sep, label)
        else:
            label = entry[1]
            label.fit(text, width)
        if tooltip is not None:
            label.tooltip.text = tooltip
        self._relayout()
        return label

    def clear_segment(self, key):
        entry = self._segments.pop(key, None)
        if entry is None:
            return
        sep, label = entry
        self._order.remove(label)
        self._separators.pop(label, None)
        label.destroy()
        sep.destroy()
        self._relayout()

    # ---- 左区排布 ----
    def _new_separator(self):
        return ttk.Label(self.left_zone, text=STATUS_BAR_SEPARATOR, style=SEGMENT_STYLE, font=STATUS_BAR_FONT)

    def _adopt_guests(self):
        """别的模块直接摆进左区的控件也算一段：记下它排在哪两段之间。"""
        packed = self.left_zone.pack_slaves()
        mine = set(self._order) | set(self._separators.values())
        for index, widget in enumerate(packed):
            if widget in mine:
                continue
            position = 0
            for earlier in reversed(packed[:index]):
                if earlier in self._order:
                    position = self._order.index(earlier) + 1
                    break
            # 紧跟在后、此刻没摆出来的空段登记得比它早，排在它前面
            while position < len(self._order) and self._order[position] not in packed:
                position += 1
            self._order.insert(position, widget)
            self._guests.add(widget)
            self._separators[widget] = self._new_separator()
            widget.bind('<Configure>', self._queue_relayout, add='+')
            mine.add(widget)

    def _drop_dead_guests(self):
        for widget in [w for w in self._guests if not w.winfo_exists()]:
            self._guests.discard(widget)
            self._order.remove(widget)
            self._separators.pop(widget).destroy()

    def _pad(self, widget):
        value = widget.pack_info().get('padx', 0)
        parts = value if isinstance(value, (tuple, list)) else str(value).split()
        pixels = [widget.winfo_pixels(str(part)) for part in parts] or [0]
        return pixels[0], pixels[-1]

    def _queue_relayout(self, _event=None):
        if self._relayout_queued or self._destroyed:
            return
        self._relayout_queued = True
        self._after(1, self._run_queued_relayout)

    def _run_queued_relayout(self):
        self._relayout_queued = False
        self._relayout()

    def _relayout(self):
        """按登记顺序把左区摆一遍：没内容的不占位，看得见的两两之间放一个分隔符。

        外来控件摆不摆由它的主人定，本栏只统一它两侧的留白；它没有内容（宽度不到 2 像素）时不配分隔符。
        """
        if self._destroyed:
            return
        self._drop_dead_guests()
        self._adopt_guests()
        packed = self.left_zone.pack_slaves()
        gap = (STATUS_BAR_SEPARATOR_GAP, STATUS_BAR_SEPARATOR_GAP)
        flush = (SPACING['none'], SPACING['none'])
        wanted, shown = [], False
        for widget in self._order:
            if widget in self._guests:
                placed = widget in packed
                visible = placed and widget.winfo_reqwidth() > 1
            else:
                placed = visible = bool(widget.full_text)
            if visible and shown:
                wanted.append((self._separators[widget], gap))
            if placed:
                wanted.append((widget, flush))
            shown = shown or visible
        if [(widget, self._pad(widget)) for widget in packed] == wanted:
            return
        keep = {widget for widget, _pad in wanted}
        for widget in packed:
            if widget not in keep:
                widget.pack_forget()
        previous = None
        for widget, pad in wanted:
            if previous is not None:
                widget.pack(side='left', padx=pad, after=previous)
            else:
                first = (self.left_zone.pack_slaves() or [widget])[0]
                if first is widget:
                    widget.pack(side='left', padx=pad)
                else:
                    widget.pack(side='left', padx=pad, before=first)
            previous = widget

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
        colors = {
            'info': (COLORS['background_primary'], COLORS['text_primary']),
            'success': (COLORS['success_subtle'], COLORS['success_text']),
            'warning': (COLORS['primary_subtle'], COLORS['primary_pressed']),
            'error': (COLORS['danger_subtle'], COLORS['danger_text']),
        }[message.level]
        self.message.configure(background=colors[0], foreground=colors[1])
        prefix = LEVEL_PREFIX[message.level]
        self.message.set_text(prefix + ' ' + message.text if prefix != '·' else message.text)

    def _show_neutral(self):
        # 中性提示和左区各段同一档灰；有消息时才换成该级别的底色和字色
        self.message.configure(background=COLORS['background_primary'], foreground=MUTED_TEXT)
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
