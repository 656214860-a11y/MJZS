# -*- coding: utf-8 -*-
"""UsageIndicator／用量详情弹窗：标签文本、隐藏规则、三档颜色、点击弹窗、CSV 导出、几何不重叠。

含 Tk，须经 ``工作流任务/gui_hidden.py`` 在隐藏桌面运行。
"""
import tempfile
import time
import unittest
from pathlib import Path

import tkinter as tk

from pet_ui_support import PATCH_X
from ui_tokens import COLORS, PET_LAYOUT
from usage_snapshot import get_snapshot
from ui_usage_detail import TodayDetailsDialog, UsageDetailDialog
from ui_usage_indicator import UsageIndicator, place_in_title_row


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
        self.assertEqual(texts['token'], 'Token:1.2K')
        self.assertEqual(texts['money'], '¥0.82')
        self.assertFalse(self._packed('balance'))

    def test_small_numbers_stay_raw(self):
        self.snapshot.record_call('a', 'm', 999)
        self.indicator.refresh()
        self.assertEqual(self._texts()['token'], 'Token:999')

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

    def test_indicator_does_not_overlap_avatar_geometry(self):
        layer = tk.Frame(self.root, width=800, height=PATCH_ROOM_FOR_TEST)
        layer.pack()
        avatar = tk.Canvas(layer, width=PET_LAYOUT['avatar_size'],
                           height=PET_LAYOUT['avatar_size'], bd=0,
                           highlightthickness=0)
        avatar.place(relx=1.0, rely=0.0, anchor='ne', x=PATCH_X,
                     y=PET_LAYOUT['top'])
        indicator = UsageIndicator(layer, self.desktop)
        place_in_title_row(indicator, layer)
        self.root.update()
        ind_right = indicator.winfo_rootx() + indicator.winfo_width()
        ava_left = avatar.winfo_rootx()
        self.assertLessEqual(ind_right, ava_left,
                             '指示器右沿 %d 压到头像左沿 %d' % (ind_right, ava_left))
        self.assertGreater(indicator.winfo_width(), 0)
        indicator.destroy()
        layer.destroy()


PATCH_ROOM_FOR_TEST = 120


if __name__ == '__main__':
    unittest.main()
