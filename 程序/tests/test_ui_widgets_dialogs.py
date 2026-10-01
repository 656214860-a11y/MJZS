"""统一弹窗的 Tk 行为回归。"""
from __future__ import annotations

import tkinter as tk
import unittest
from tkinter import ttk

from ui_widgets import BaseDialog, ConfirmDialog, FormDialog


class DialogWidgetTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest('Tk display unavailable: ' + str(exc))

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.destroy()

    def test_form_dialog_hosts_fields_and_submit_cancel_actions(self):
        submitted = []
        dialog = FormDialog(self.root, '填写创作信息')
        field = ttk.Entry(dialog.content)
        field.insert(0, '故事梗概')
        field.pack()
        submit = dialog.add_form_actions('确定', lambda: submitted.append(field.get()))
        submit.invoke()
        self.assertEqual(submitted, ['故事梗概'])
        dialog.close()
        self.assertFalse(dialog.winfo_exists())

    def test_confirm_dialog_dangerous_branch_returns_confirmation(self):
        outcomes = []
        dialog = ConfirmDialog(self.root, '危险操作', '确认删除？', dangerous=True,
                               on_result=outcomes.append)
        dialog._confirm()
        self.assertTrue(dialog.result)
        self.assertEqual(outcomes, [True])

    def test_escape_closes_and_releases_modal_grab(self):
        dialog = BaseDialog(self.root, '关闭测试')
        self.root.update()
        self.assertEqual(dialog.grab_current(), dialog)
        dialog.event_generate('<Escape>')
        self.root.update()
        self.assertIsNone(self.root.grab_current())
        self.assertFalse(dialog.winfo_exists())
