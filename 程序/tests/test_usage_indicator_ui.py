# -*- coding: utf-8 -*-
"""UsageIndicator／用量详情弹窗：标签文本、隐藏规则、三档颜色、点击弹窗、CSV 导出、几何不重叠。

含 Tk，由运行器自动隐藏桌面执行（scripts/gui_hidden.py）。
"""
import tempfile
import time
import unittest
from pathlib import Path

import tkinter as tk
from tkinter import font as tkfont

from ui_tokens import COLORS, SPACING, STATUS_BAR_FONT, STATUS_BAR_SEPARATOR, STATUS_BAR_SEPARATOR_GAP
from infra.usage_snapshot import get_snapshot
from ui.ui_status_bar import StatusBar
from ui.ui_status_bus import StatusBus
from ui.ui_usage_detail import TodayDetailsDialog, UsageDetailDialog
from ui.ui_usage_indicator import UsageIndicator


class _Status:
    """desktop.status（tk.StringVar）的最小替身。"""

    def __init__(self):
        self.text = ''

    def set(self, value):
        self.text = value

    def get(self):
        return self.text


class _Desktop:
    """指示器只需要 desktop.root（项目路径）与 desktop.pet（可为空）。"""

    def __init__(self, project, win):
        self.root = project
        self.pet = None
        self.win = win
        self.status = _Status()


class UsageIndicatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.desktop = _Desktop(self.project, self.root)
        self.indicator = UsageIndicator(self.root, self.desktop)
        self.addCleanup(self.indicator.destroy)
        self.snapshot = get_snapshot(self.project)

    def _texts(self):
        return {key: label.cget('text') for key, label in self.indicator._labels.items()}

    def _packed(self, key):
        return self.indicator._labels[key].winfo_manager() != ''

    def test_refresh_shows_token_money_and_hides_balance(self):
        self.snapshot.record_call('script', 'gpt-x', 1200, cost='0.82', currency='CNY')
        self.indicator.refresh()
        texts = self._texts()
        self.assertEqual(texts['token'], 'Token: 1.2K')
        self.assertEqual(texts['money'], '¥0.82')
        self.assertFalse(self._packed('balance'))

    def test_small_numbers_stay_raw(self):
        self.snapshot.record_call('a', 'm', 999)
        self.indicator.refresh()
        self.assertEqual(self._texts()['token'], 'Token: 999')

    def test_no_price_table_and_no_balance_hide_items_without_fake_zero(self):
        self.snapshot.record_call('a', 'm', 500)
        self.indicator.refresh()
        self.assertFalse(self._packed('money'))
        self.assertFalse(self._packed('balance'))
        texts = self._texts()
        self.assertNotIn('¥0', texts['money'])
        self.assertNotIn('余额', texts['balance'])

    def test_balance_shows_when_available(self):
        self.snapshot._balance = {'amount': '9', 'currency': 'CNY'}
        self.snapshot.record_call('a', 'm', 10, cost='0.5', currency='CNY')
        self.indicator.refresh()
        self.assertTrue(self._packed('balance'))
        self.assertEqual(self._texts()['balance'], '余额：¥9')

    def test_token_color_thresholds(self):
        cases = [(499999, COLORS['success_text']),
                 (500000, COLORS['warning_text']),
                 (1500000, COLORS['danger_text'])]
        made = 0
        for target, _color in cases:
            need = target - made
            if need > 0:
                self.snapshot.record_call('a', 'm', need)
                made = target
            self.indicator.refresh()
            self.assertEqual(self.indicator._labels['token'].cget('fg'), _color,
                             'tokens=%d' % target)

    def test_click_opens_detail_dialog(self):
        self.snapshot.record_call('a', 'm', 100, cost='0.1', currency='CNY')
        self.indicator._open_detail()
        self.root.update()
        dialogs = [w for w in self.root.winfo_children()
                   if isinstance(w, UsageDetailDialog)]
        self.assertEqual(len(dialogs), 1)
        dialogs[0].close()
        self.root.update()

    def test_csv_export_writes_utf8_sig(self):
        self.snapshot.record_call('script', 'gpt-x', 1200)
        self.snapshot.record_call('assets', 'gpt-y', 300)
        dialog = TodayDetailsDialog(self.root, self.desktop)
        self.addCleanup(dialog.close)
        dialog._export_csv()
        target = self.project / ('今日调用明细_%s.csv' % time.strftime('%Y%m%d'))
        self.assertTrue(target.is_file(), '未写到项目目录固定文件名')
        raw = target.read_bytes()
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'), '缺 UTF-8-SIG BOM')
        text = raw.decode('utf-8-sig')
        self.assertIn('时间,阶段,模型,Token', text)
        self.assertIn('script,gpt-x,1200', text)
        self.assertIn('assets,gpt-y,300', text)
        self.assertIn('已导出', self.desktop.status.get())

    def test_indicator_labels_pack_horizontally_for_the_title_row(self):
        """R2933 建、R3016 改：指示器 pack 进统一底栏左区、Token/费用/余额同一行从左到右排开。"""
        self.snapshot.record_call('a', 'm', 1200, cost='0.82', currency='CNY')
        self.indicator.refresh()
        self.root.update()
        labels = [label for label in self.indicator._labels.values() if label.winfo_manager()]
        self.assertEqual(len(labels), 2, 'Token 与金额两项都该排出来')
        for label in labels:
            self.assertEqual(label.pack_info()['side'], 'left')
            self.assertGreater(label.winfo_width(), 0)
        tops = {label.winfo_rooty() for label in labels}
        self.assertEqual(len(tops), 1, '三段标签必须在同一行')

    @staticmethod
    def _pad(label):
        value = label.pack_info()['padx']
        parts = value if isinstance(value, (tuple, list)) else str(value).split()
        pixels = [label.winfo_pixels(str(part)) for part in parts]
        return pixels[0], pixels[-1]

    def test_labels_use_the_status_bar_font(self):
        """UX-C4：三项和状态栏的其他段同一字体、同一字号。"""
        wanted = tkfont.Font(root=self.root, font=STATUS_BAR_FONT).actual()
        for key, label in self.indicator._labels.items():
            with self.subTest(label=key):
                self.assertEqual(tkfont.Font(root=self.root, font=label.cget('font')).actual(), wanted)

    def test_group_has_no_outer_padding_and_one_gap_inside(self):
        """UX-C4：整组两端不留白（两侧的间距由状态栏统一给），组内相邻两项之间一档间距。"""
        self.snapshot._balance = {'amount': '9', 'currency': 'CNY'}
        self.snapshot.record_call('a', 'm', 1200, cost='0.82', currency='CNY')
        self.indicator.refresh()
        pads = [self._pad(self.indicator._labels[key]) for key in ('token', 'money', 'balance')]
        self.assertEqual(pads, [(0, 0), (SPACING['sm'], 0), (SPACING['sm'], 0)])

    def test_inside_the_status_bar_the_group_keeps_the_same_gap_on_both_sides(self):
        """UX-C4：摆进底栏左区后，前后各一个分隔符，分隔符到这一组文字的距离和别的段一样。"""
        bar = StatusBar(self.root, StatusBus())
        bar.pack(fill='x')
        self.addCleanup(bar.destroy)
        self.addCleanup(bar.shutdown)
        bar.set_segment('page', '01 创意')
        bar.set_segment('path', '')
        indicator = UsageIndicator(bar.left_zone, self.desktop)
        indicator.pack(side='left', padx=(SPACING['xs'], SPACING['none']))  # 和 desktop.py 的摆法一样
        bar.set_segment('model', '模型：甲')
        self.snapshot.record_call('a', 'm', 1200, cost='0.82', currency='CNY')
        indicator.refresh()
        end = time.monotonic() + 0.3
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.005)
        row = sorted((w for w in bar.left_zone.winfo_children() if w.winfo_manager() and w.winfo_width() > 1),
                     key=lambda w: w.winfo_x())
        self.assertEqual(len(row), 5, [str(w) for w in row])
        self.assertIs(row[2], indicator)
        self.assertEqual([str(w.cget('text')) for w in (row[1], row[3])], [STATUS_BAR_SEPARATOR] * 2)
        first, last = indicator._labels['token'], indicator._labels['money']
        before = first.winfo_rootx() - (row[1].winfo_rootx() + row[1].winfo_width())
        after = row[3].winfo_rootx() - (last.winfo_rootx() + last.winfo_width())
        self.assertEqual((before, after), (STATUS_BAR_SEPARATOR_GAP, STATUS_BAR_SEPARATOR_GAP))


if __name__ == '__main__':
    unittest.main()
