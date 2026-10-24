"""下拉框空值占位“请选择”（R2002）：只读下拉框取值为空时显示占位，取值本身不变。

含 Tk，须经 ``工作流任务/gui_hidden.py`` 在隐藏桌面运行。
"""
from __future__ import annotations

import tkinter as tk
import unittest

from ui_tokens import COMBOBOX_PLACEHOLDER
from ui_widgets import SelectBox


class SelectPlaceholderTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)

    def shown(self, box):
        self.root.update()
        return box._hint is not None and box._hint.winfo_ismapped()

    def test_empty_value_shows_placeholder_without_changing_value(self):
        var = tk.StringVar(self.root, '')
        box = SelectBox(self.root, textvariable=var, values=['甲', '乙'])
        box.pack()
        self.assertTrue(self.shown(box))
        self.assertEqual(box._hint.cget('text'), COMBOBOX_PLACEHOLDER)
        self.assertEqual((var.get(), box.get()), ('', ''))

    def test_placeholder_follows_value(self):
        var = tk.StringVar(self.root, '')
        box = SelectBox(self.root, textvariable=var, values=['甲', '乙'])
        box.pack()
        var.set('甲')
        self.assertFalse(self.shown(box))
        var.set('')
        self.assertTrue(self.shown(box))

    def test_existing_default_is_untouched(self):
        box = SelectBox(self.root, textvariable=tk.StringVar(self.root, '乙'), values=['甲', '乙'])
        box.pack()
        self.assertFalse(self.shown(box))
        self.assertEqual(box.get(), '乙')

    def test_box_without_variable_gets_own_one(self):
        box = SelectBox(self.root, values=['甲'])
        box.pack()
        self.assertTrue(self.shown(box))
        box.set('甲')
        self.assertFalse(self.shown(box))

    def test_editable_box_has_no_placeholder(self):
        box = SelectBox(self.root, values=['甲'], state='normal')
        self.assertIsNone(box._hint)


if __name__ == '__main__':
    unittest.main()
