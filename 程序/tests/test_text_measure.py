"""U1 共享测宽 ``ui_popup.measure_text_width`` 与 SelectBox 自适应宽度（真 Tk 几何）。

含 Tk，由运行器自动隐藏桌面执行（scripts/gui_hidden.py）。
"""
from __future__ import annotations

import tkinter as tk
import unittest

from ui import ui_popup
from ui_tokens import COMBOBOX_FONT, COMBOBOX_MAX_WIDTH, FONTS
from ui_widgets import SelectBox, _display_width


class MeasureTextWidthTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)

    def test_fullwidth_ascii_mixed_empty_and_clamp(self):
        font = FONTS['body']
        self.assertGreater(ui_popup.measure_text_width(font, ['中文标题']), 0)
        self.assertGreater(ui_popup.measure_text_width(font, ['plain ASCII']), 0)
        mixed = ui_popup.measure_text_width(font, ['中a文B9'])
        self.assertGreater(mixed, ui_popup.measure_text_width(font, ['中a文B9'.replace('中', '')]))
        self.assertEqual(ui_popup.measure_text_width(font, ['']), 0)
        self.assertEqual(ui_popup.measure_text_width(font, []), 0)
        wide = '很长的选项名称' * 30
        px = ui_popup.measure_text_width(font, [wide])
        self.assertLessEqual(ui_popup.measure_text_width(font, [wide], max_width=200), 200)
        self.assertEqual(ui_popup.measure_text_width(font, [wide], max_width=px + 50), px)
        self.assertGreater(px, 200)

    def test_collection_returns_longest(self):
        font = FONTS['body']
        self.assertEqual(
            ui_popup.measure_text_width(font, ['a', '中文标题', 'ab']),
            ui_popup.measure_text_width(font, ['中文标题']))

    def test_units_width_ceils_and_scales_with_text(self):
        font = FONTS['body']
        short = ui_popup.text_units_width(font, ['ab'])
        long_cjk = ui_popup.text_units_width(font, ['中文标题中文标题'])
        self.assertGreaterEqual(short, 1)
        self.assertGreater(long_cjk, short)


class SelectBoxFitWidthTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)

    def test_long_cjk_options_fit_within_cap(self):
        longest = '这是一个比较长的选项'
        values = ['短', longest, '中等长度选项']
        box = SelectBox(self.root, values=values, fit=True)
        box.pack()
        self.root.update()
        width_chars = int(box.cget('width'))
        self.assertLessEqual(width_chars, COMBOBOX_MAX_WIDTH)
        self.assertEqual(width_chars, _display_width(longest))
        self.assertGreater(box.winfo_width(), 0)
        over = SelectBox(self.root, values=['字' * 40], fit=True)
        over.pack()
        self.root.update()
        self.assertEqual(int(over.cget('width')), COMBOBOX_MAX_WIDTH)

    def test_short_options_stay_compact(self):
        box = SelectBox(self.root, values=['甲', '乙'], fit=True)
        box.pack()
        self.root.update()
        self.assertLessEqual(int(box.cget('width')), COMBOBOX_MAX_WIDTH)
        self.assertGreater(int(box.cget('width')), 0)


if __name__ == '__main__':
    unittest.main()
