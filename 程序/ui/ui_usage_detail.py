# -*- coding: utf-8 -*-
"""用量详情弹窗（费用统计模块任务书）。

``UsageDetailDialog``：今日汇总＋当前项目累计＋可选余额；
``TodayDetailsDialog``：今日调用明细表格（统一 ``DataTable``）与 UTF-8-SIG CSV 导出。
不做图表、趋势与长期明细。
"""
import csv
import io
import time
from pathlib import Path

from tkinter import ttk

import infra.app_logging as app_logging
from agent.core import save_text
from ui_tokens import FONTS, SPACING, TEXT_ROWS
from ui_widgets import BaseDialog, DataTable, notify
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
            ttk.Label(body, text=label + '：', font=FONTS['pet_hint']).grid(
                row=index, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
            ttk.Label(body, text=text, font=FONTS['body']).grid(
                row=index, column=1, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        bamount = money_amount(balance.get('amount')
                               if isinstance(balance, dict) else None)
        if bamount is not None:
            row = len(rows)
            bcurrency = balance.get('currency') if isinstance(balance, dict) else ''
            ttk.Label(body, text='余额：', font=FONTS['pet_hint']).grid(
                row=row, column=0, sticky='w')
            ttk.Label(body, text=money_text(bamount, bcurrency),
                      font=FONTS['body']).grid(row=row, column=1, sticky='w')
        self.add_action('查看今日明细',
                        lambda: TodayDetailsDialog(self, self.desktop))
        self.add_action('关闭', self.close, primary=True)

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
        self.add_action('关闭', self.close, primary=True)

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
            notify(self, '导出失败：' + str(exc), level='error', title='导出 CSV')
            return
        status = getattr(self.desktop, 'status', None)
        try:
            if status is not None:
                status.set('已导出今日调用明细：' + str(target))
        except Exception:
            app_logging.swallowed()
