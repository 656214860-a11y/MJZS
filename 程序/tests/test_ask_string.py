"""ask_string 统一文本输入弹窗的 Tk 行为回归。

入口 ``ui_widgets.ask_string(parent, title, prompt, *, initialvalue="") -> str | None``
必须区分三种返回：确认返回输入（空串＝用户明确留空）、取消／Esc／关闭返回 ``None``。
"""
from __future__ import annotations

import tkinter as tk
import unittest

from skip_reasons import PLATFORM_TK_DISPLAY
from ui_widgets import StringDialog, ask_string


class AskStringTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))

    def tearDown(self):
        if hasattr(self, 'root'):
            try:
                holder = self.root.grab_current()
                if holder is not None:
                    holder.grab_release()
            except tk.TclError:
                pass
            self.root.destroy()

    def _dialog(self):
        return next(child for child in self.root.winfo_children()
                    if isinstance(child, StringDialog))

    def test_initial_value_is_prefilled_and_confirm_returns_it(self):
        seen = {}

        def interact():
            dialog = self._dialog()
            seen['value'] = dialog.entry.get()
            dialog._confirm()

        self.root.after_idle(interact)
        result = ask_string(self.root, '标题', '提示', initialvalue='预填')
        self.assertEqual(seen['value'], '预填')
        self.assertEqual(result, '预填')

    def test_confirm_returns_input(self):
        def interact():
            dialog = self._dialog()
            dialog.entry.delete(0, 'end')
            dialog.entry.insert(0, '我的输入')
            dialog._confirm()

        self.root.after_idle(interact)
        self.assertEqual(ask_string(self.root, '标题', '提示'), '我的输入')

    def test_empty_input_returns_empty_string(self):
        """用户确认空输入必须返回 ''，与取消返回的 None 严格区分。"""

        def interact():
            self._dialog()._confirm()

        self.root.after_idle(interact)
        self.assertEqual(ask_string(self.root, '标题', '提示'), '')

    def test_cancel_returns_none(self):
        def interact():
            self._dialog().close()

        self.root.after_idle(interact)
        self.assertIsNone(ask_string(self.root, '标题', '提示'))

    def test_escape_returns_none(self):
        def interact():
            self._dialog()._on_escape()

        self.root.after_idle(interact)
        self.assertIsNone(ask_string(self.root, '标题', '提示'))

    def test_dialog_is_modal_to_parent(self):
        seen = {}

        def interact():
            dialog = self._dialog()
            seen['master'] = dialog.master
            seen['grab_is_dialog'] = dialog.grab_current() is dialog
            dialog.close()

        self.root.after_idle(interact)
        ask_string(self.root, '标题', '提示')
        self.assertIs(seen['master'], self.root)
        self.assertTrue(seen['grab_is_dialog'])
