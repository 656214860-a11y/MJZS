# -*- coding: utf-8 -*-
"""用量悬停卡片与明细弹窗（费用统计模块任务书）。

``UsageHoverCard``：底部状态栏用量指示器的被动悬停卡片（今日汇总＋项目累计＋可选余额＋今日明细入口）；
``UsageDetailDialog``：向后兼容保留的旧版用量详情弹窗；
``TodayDetailsDialog``：今日调用明细表格（统一 ``DataTable``）与 UTF-8-SIG CSV 导出。
不做图表、趋势与长期明细。
"""
import csv
import io
import time
from pathlib import Path

from tkinter import TclError, ttk

import infra.app_logging as app_logging
from contract import error_codes
from agent.core import save_text
from ui_tokens import SPACING, TEXT_ROWS, TOOLTIP_BORDER_WIDTH
from ui_widgets import BaseDialog, DataTable, HintLabel, SecondaryButton, Tooltip, notify
from infra.usage_snapshot import get_snapshot, money_amount, money_text


def _tokens_text(tokens):
    n = int(tokens or 0)
    return '%s (%s万)' % (format(n, ','), format(n / 10000, '.1f'))


def _calls_text(calls):
    return '%s 次' % int(calls or 0)


def _aggregate_text(row, currency):
    """一行汇总：``Token 1,234（0.1万） · ¥0.82 · 3 次``；无金额时省略 ¥ 段。"""
    parts = ['Token ' + _tokens_text(row.get('token_used')),
             _calls_text(row.get('total_calls', row.get('calls')))]
    amount = money_amount(row.get('money_spent'))
    if amount is not None:
        parts.insert(1, money_text(amount, currency))
    return ' · '.join(parts)


def _snapshot_data(desktop):
    root = getattr(desktop, 'root', None)
    if root is None:
        return {}
    try:
        return get_snapshot(root).current() or {}
    except Exception:
        return {}


def _overview_fields(data):
    today = data.get('today') or {}
    total = data.get('project_total') or {}
    currency = data.get('currency') or ''
    balance = data.get('balance') or {}
    today_text = _aggregate_text(today, currency)
    total_text = _aggregate_text(total, currency)
    bamount = money_amount(balance.get('amount')
                           if isinstance(balance, dict) else None)
    bcurrency = balance.get('currency') if isinstance(balance, dict) else ''
    balance_text = money_text(bamount, bcurrency) if bamount is not None else None
    return today_text, total_text, balance_text


def _summary_text(today_text, total_text, balance_text):
    lines = ['用量概览', '今日：' + today_text, '项目累计：' + total_text]
    if balance_text is not None:
        lines.append('余额：' + balance_text)
    return '\n'.join(lines)


class UsageHoverCard(Tooltip):
    """底部用量指示器的被动悬停卡片：实时渲染用量概览与今日明细轻量入口。"""

    def __init__(self, indicator, desktop, **opts):
        self.desktop = desktop
        self._grid = None
        self._today_label = None
        self._total_label = None
        self._balance_widgets = ()
        self._details_button = None
        opts.setdefault('mode', 'card')
        opts.setdefault('pin_on_click', False)
        super().__init__(indicator, '用量概览', **opts)
        self._sync_summary()
        for child in self._bound_children(indicator):
            child.bind('<Enter>', self._schedule_from_pointer, add='+')
            child.bind('<Leave>', self._leave, add='+')
            child.bind('<FocusIn>', self._schedule_from_focus, add='+')
            child.bind('<FocusOut>', self._focus_out, add='+')
            child.bind('<Button-1>', self._press, add='+')

    @staticmethod
    def _bound_children(indicator):
        labels = getattr(indicator, '_labels', None)
        if isinstance(labels, dict):
            return tuple(labels.values())
        return ()

    def _data(self):
        return _snapshot_data(self.desktop)

    def _sync_summary(self):
        fields = _overview_fields(self._data())
        self.text = _summary_text(*fields)
        return fields

    def _set_balance_row(self, balance_text):
        if self._grid is None:
            return
        if balance_text is None:
            for widget in self._balance_widgets:
                try:
                    widget.destroy()
                except TclError:
                    pass
            self._balance_widgets = ()
            return
        if self._balance_widgets:
            self._balance_widgets[1].configure(text=balance_text)
            return
        key_label = HintLabel(self._grid, text='余额：')
        key_label.grid(row=2, column=0, sticky='w',
                       pady=(SPACING['none'], SPACING['xs']))
        val_label = ttk.Label(self._grid, text=balance_text)
        val_label.grid(row=2, column=1, sticky='w',
                       padx=(SPACING['xs'], SPACING['none']),
                       pady=(SPACING['none'], SPACING['xs']))
        self._balance_widgets = (key_label, val_label)

    def _populate(self, tip):
        today_text, total_text, balance_text = self._sync_summary()
        card = ttk.Frame(tip, style='Card.TFrame',
                         padding=(SPACING['md'], SPACING['sm']))
        card.pack(fill='both', expand=True,
                  padx=TOOLTIP_BORDER_WIDTH, pady=TOOLTIP_BORDER_WIDTH)
        ttk.Label(card, text='用量概览', style='CardHeading.TLabel').pack(
            anchor='w', pady=(SPACING['none'], SPACING['xs']))
        grid = ttk.Frame(card, style='Card.TFrame')
        grid.pack(fill='x')
        self._grid = grid
        HintLabel(grid, text='今日：').grid(
            row=0, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        self._today_label = ttk.Label(grid, text=today_text)
        self._today_label.grid(row=0, column=1, sticky='w',
                               padx=(SPACING['xs'], SPACING['none']),
                               pady=(SPACING['none'], SPACING['xs']))
        HintLabel(grid, text='项目累计：').grid(
            row=1, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        self._total_label = ttk.Label(grid, text=total_text)
        self._total_label.grid(row=1, column=1, sticky='w',
                               padx=(SPACING['xs'], SPACING['none']),
                               pady=(SPACING['none'], SPACING['xs']))
        self._balance_widgets = ()
        self._set_balance_row(balance_text)
        ttk.Separator(card, orient='horizontal').pack(
            fill='x', pady=(SPACING['xs'], SPACING['xs']))
        actions = ttk.Frame(card, style='Card.TFrame')
        actions.pack(fill='x')
        self._details_button = SecondaryButton(
            actions, text='查看今日明细', width=0,
            style='Tokens.Text.TButton', command=self._open_today_details)
        self._details_button.pack(side='right')
        return None

    def refresh(self):
        today_text, total_text, balance_text = self._sync_summary()
        if self._window is None:
            return
        try:
            if not self._window.winfo_exists():
                self._clear_refs()
                super().refresh()
                return
            if self._today_label is not None:
                self._today_label.configure(text=today_text)
            if self._total_label is not None:
                self._total_label.configure(text=total_text)
            self._set_balance_row(balance_text)
        except TclError:
            self._clear_refs()
            return
        super().refresh()

    def hide(self, _event=None):
        self._clear_refs()
        super().hide(_event)

    def _clear_refs(self):
        self._grid = None
        self._today_label = None
        self._total_label = None
        self._balance_widgets = ()
        self._details_button = None

    def _open_today_details(self):
        try:
            parent = self.widget.winfo_toplevel()
            self.hide()
            TodayDetailsDialog(parent, self.desktop)
        except Exception:
            app_logging.swallowed()


class UsageDetailDialog(BaseDialog):
    """今日汇总＋项目累计的只读详情；「查看今日明细」进入调用级表格。"""

    def __init__(self, parent, desktop):
        self.desktop = desktop
        data = self._data()
        super().__init__(parent, '用量详情', geometry='460x240')
        body = ttk.Frame(self.content)
        body.pack(fill='both', expand=True)
        today = data.get('today') or {}
        total = data.get('project_total') or {}
        currency = data.get('currency') or ''
        balance = data.get('balance') or {}
        rows = [('今日', _aggregate_text(today, currency)),
                ('项目累计', _aggregate_text(total, currency))]
        for index, (label, text) in enumerate(rows):
            HintLabel(body, text=label + '：').grid(
                row=index, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
            ttk.Label(body, text=text).grid(
                row=index, column=1, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        bamount = money_amount(balance.get('amount')
                               if isinstance(balance, dict) else None)
        if bamount is not None:
            row = len(rows)
            bcurrency = balance.get('currency') if isinstance(balance, dict) else ''
            HintLabel(body, text='余额：').grid(row=row, column=0, sticky='w')
            ttk.Label(body, text=money_text(bamount, bcurrency)).grid(
                row=row, column=1, sticky='w')
        self.add_action('查看今日明细',
                        lambda: TodayDetailsDialog(self, self.desktop))
        self.add_action('关闭', self.close)

    def _data(self):
        root = getattr(self.desktop, 'root', None)
        if root is None:
            return {}
        return get_snapshot(root).current()


class TodayDetailsDialog(BaseDialog):
    """今日每笔模型调用一行：时间／阶段／模型／Token；可导出 UTF-8-SIG CSV。"""

    COLUMNS = (('at', '时间', 90), ('stage', '阶段', 90),
               ('model', '模型', 160), ('tokens', 'Token', 90))

    def __init__(self, parent, desktop):
        self.desktop = desktop
        super().__init__(parent, '今日用量明细', geometry='560x380')
        self._rows = self._details()
        body = ttk.Frame(self.content)
        body.pack(fill='both', expand=True)
        self.table = DataTable(body, columns=list(self.COLUMNS), show='headings',
                               height=TEXT_ROWS['2xl'], empty_text='今日还没有模型调用')
        self.table.pack(fill='both', expand=True)
        for row in self._rows:
            self.table.tree.insert('', 'end', values=(row.get('at', ''), row.get('stage', ''),
                                                      row.get('model', ''),
                                                      format(int(row.get('tokens') or 0), ',')))
        self.add_action('导出 CSV', self._export_csv)
        self.add_action('关闭', self.close)

    def _details(self):
        root = getattr(self.desktop, 'root', None)
        if root is None:
            return []
        try:
            today = (get_snapshot(root).current().get('today') or {})
            rows = today.get('details') or []
            return [dict(row) for row in rows]
        except Exception:
            return []

    def _csv_text(self):
        buffer = io.StringIO()
        # lineterminator='\n'：save_text 文本写入在 Windows 上会把 \n 翻成 \r\n，
        # 若用 csv 默认的 \r\n 会落成 \r\r\n。
        writer = csv.writer(buffer, lineterminator='\n')
        writer.writerow(['时间', '阶段', '模型', 'Token'])
        for row in self._rows:
            writer.writerow([row.get('at', ''), row.get('stage', ''),
                             row.get('model', ''), int(row.get('tokens') or 0)])
        return buffer.getvalue()

    def _write_csv(self, target):
        save_text(Path(target), self._csv_text(), encoding='utf-8-sig')

    def _export_csv(self):
        """任务书口径：直接写 ``<项目>/今日调用明细_YYYYMMDD.csv``（UTF-8-SIG），状态栏提示。"""
        root = getattr(self.desktop, 'root', None)
        if root is None:
            return
        target = Path(root) / ('今日调用明细_%s.csv' % time.strftime('%Y%m%d'))
        try:
            self._write_csv(target)
        except (OSError, ValueError) as exc:
            notify(self, '导出失败：' + error_codes.user_text(exc), level='error', title='导出 CSV')
            return
        status = getattr(self.desktop, 'status', None)
        try:
            if status is not None:
                status.set('已导出今日调用明细：' + str(target))
        except Exception:
            app_logging.swallowed()
