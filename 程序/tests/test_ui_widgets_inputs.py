"""统一输入组件的 Tk 行为回归。"""
from __future__ import annotations

import tkinter as tk
import unittest

from skip_reasons import PLATFORM_TK_DISPLAY
from ui_widgets import LineInput, TextArea


class InputWidgetTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_line_input_hides_placeholder_and_exposes_error_and_readonly_states(self):
        field = LineInput(self.root, placeholder="项目名称")
        field.pack()
        self.root.update()
        self.assertEqual(field.get(), "")
        field.insert(0, "新项目")
        self.assertEqual(field.get(), "新项目")
        field.set_error("名称重复")
        self.assertEqual(field.error_message, "名称重复")
        self.assertEqual(field.cget("style"), LineInput.ERROR_STYLE)
        field.clear_error()
        field.set_readonly(True)
        self.assertIn("readonly", field.state())

    def test_text_area_preserves_text_api_and_unifies_placeholder_error_and_readonly(self):
        area = TextArea(self.root, placeholder="填写梗概", height=2)
        area.pack()
        self.root.update()
        self.assertEqual(area.get("1.0", "end-1c"), "")
        area.insert("1.0", "故事梗概")
        self.assertEqual(area.get("1.0", "end-1c"), "故事梗概")
        area.set_error("必填")
        self.assertEqual(area.error_message, "必填")
        area.set_readonly(True)
        self.assertEqual(str(area.cget("state")), "disabled")
