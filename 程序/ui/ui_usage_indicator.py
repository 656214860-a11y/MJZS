# -*- coding: utf-8 -*-
"""页标题右侧用量指示器（费用统计模块任务书）。

第 R2933 期：从标题行右上角浮层改为 pack 进标题行、紧跟页标题同一行；
显示今日 Token 用量、今日费用（仅在有价格表折算出非零金额时）与平台余额
（查不到就隐藏，绝不显示假 0）。Token 颜色按日用量三档取 ``ui_tokens`` 语义色。

订阅 ``pet_bus`` 的 ``usage_updated`` 事件刷新；``sync_bus()`` 由 desktop
每拍调用，保证换项目重建总线后重新绑定，不丢刷新。
"""
import tkinter as tk

import infra.app_logging as app_logging
from ui_tokens import COLORS, FONTS, SPACING
from infra.usage_snapshot import abbr_number, get_snapshot, money_amount, money_text

_TOKEN_WARN = 500000     # ≥50 万：黄色
_TOKEN_DANGER = 1500000  # ≥150 万：红色


class UsageIndicator(tk.Frame):
    """一行三个可点标签：Token／¥／余额；点击打开用量详情。"""

    def __init__(self, master, desktop):
        super().__init__(master, bg=COLORS['background_primary'])
        self.desktop = desktop
        self._bus = None
        self._labels = {}
        for key in ('token', 'money', 'balance'):
            label = tk.Label(self, text='', bg=COLORS['background_primary'],
                             fg=COLORS['text_primary'], font=FONTS['pet_hint'])
            label.pack_forget()
            label.bind('<Button-1>', self._open_detail)
            self._labels[key] = label
        self.bind('<Button-1>', self._open_detail)
        self.refresh()

    # -- 数据 -----------------------------------------------------
    def _snapshot(self):
        root = getattr(self.desktop, 'root', None)
        if root is None:
            return None
        return get_snapshot(root).current()

    @staticmethod
    def _token_color(tokens):
        if tokens >= _TOKEN_DANGER:
            return COLORS['danger_text']
        if tokens >= _TOKEN_WARN:
            return COLORS['warning_text']
        return COLORS['success_text']

    def refresh(self):
        """按快照重写三段文字；金额／余额缺数据时整项隐藏，不显示 0。"""
        try:
            data = self._snapshot()
        except Exception:
            return
        if data is None or not self.winfo_exists():
            return
        today = data.get('today') or {}
        tokens = int(today.get('token_used') or 0)
        cost = money_amount(today.get('money_spent'))
        balance = data.get('balance') or {}
        bamount = money_amount(balance.get('amount')
                               if isinstance(balance, dict) else None)
        bcurrency = balance.get('currency') if isinstance(balance, dict) else ''
        ordered = [('token', 'Token: ' + abbr_number(tokens), self._token_color(tokens))]
        if cost is not None:
            ordered.append(('money', money_text(cost, data.get('currency')), COLORS['text_primary']))
        if bamount is not None:
            ordered.append(('balance', '余额：' + money_text(bamount, bcurrency),
                            COLORS['text_primary']))
        for key, _text, _fg in ordered:
            self._labels[key].pack_forget()
        for index, (key, text, fg) in enumerate(ordered):
            label = self._labels[key]
            label.configure(text=text, fg=fg)
            label.pack(side='left', padx=(SPACING['xs'] if index else SPACING['none'],
                                         SPACING['xs']))

    # -- 事件总线 ---------------------------------------------------
    def sync_bus(self):
        """把快照发射端与本控件订阅都对齐到当前项目总线（换项目后总线会重建）。"""
        pet = getattr(self.desktop, 'pet', None)
        try:
            bus = getattr(pet, 'bus', None) if pet is not None else None
        except Exception:
            bus = None
        if bus is None or bus is self._bus:
            return
        self._bus = bus
        try:
            import infra.usage_snapshot as usage_snapshot
            usage_snapshot.bind_bus(bus, getattr(pet, 'errors', None))
        except Exception:
            app_logging.swallowed()
        try:
            bus.subscribe('usage_updated', self._on_usage_event)
        except Exception:
            app_logging.swallowed()
        self.refresh()

    def _on_usage_event(self, _item):
        try:
            if self.winfo_exists():
                self.refresh()
        except Exception:
            app_logging.swallowed()

    # -- 交互 -------------------------------------------------------
    def _open_detail(self, _event=None):
        try:
            from ui.ui_usage_detail import UsageDetailDialog
            UsageDetailDialog(self.winfo_toplevel(), self.desktop)
        except Exception:
            app_logging.swallowed()
