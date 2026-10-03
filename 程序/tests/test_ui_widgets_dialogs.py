"""统一弹窗的 Tk 行为回归。"""
from __future__ import annotations
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)

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

    def test_form_dialog_actions_keep_button_labels_visible(self):
        """动作区不能把 Windows 主题的标准按钮裁成无文字色块。"""
        dialog = FormDialog(self.root, '填写创作信息')
        submit = dialog.add_form_actions('保存并发送', lambda: None)
        dialog.update_idletasks()
        self.assertGreaterEqual(dialog.actions.winfo_reqheight(), submit.winfo_reqheight(),
                                '底部动作区的请求高度必须容纳完整按钮')
        dialog.close()

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
        # 跨 Tcl 解释器连续创建／销毁模态窗时，Windows 会把合成按键
        # 交给旧窗口管理器；直接调用已绑定的 Esc 回调仍验证同一行为。
        self.assertTrue(dialog.bind('<Escape>'))
        self.assertEqual(dialog._on_escape(), 'break')
        self.root.update()
        self.assertIsNone(self.root.grab_current())
        self.assertFalse(dialog.winfo_exists())

    def test_close_releases_current_grab_even_when_another_window_took_it(self):
        dialog = BaseDialog(self.root, '关闭测试')
        other = tk.Toplevel(self.root)
        self.root.update()
        other.grab_set()
        self.assertEqual(self.root.grab_current(), other)
        dialog.close()
        self.root.update()
        self.assertIsNone(self.root.grab_current())
        self.assertFalse(dialog.winfo_exists())
        other.destroy()
