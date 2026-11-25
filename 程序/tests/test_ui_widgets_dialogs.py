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

from ui_tokens import COLORS
from ui_popup import Flyout
from ui_widgets import BaseDialog, ConfirmDialog, FormDialog, NoticeDialog, StringDialog, ask_confirmation


class DialogWidgetTests(unittest.TestCase):
    def test_initial_placement_fits_main_but_allows_later_resize(self):
        import ui_theme
        ui_theme.install_window_placement(self.root)
        self.root.deiconify()
        self.root.update()
        self.root.geometry('640x480+0+0')
        self.root.update()
        dialog = BaseDialog(self.root, '尺寸测试', geometry='1000x800',
                            minsize=(900, 700), modal=False)
        dialog.resizable(False, False)
        dialog.maxsize(900, 700)
        self.root.update()
        self.assertLessEqual(dialog.winfo_width(), self.root.winfo_width())
        self.assertLessEqual(dialog.winfo_height(), self.root.winfo_height())
        self.assertEqual(tuple(map(bool, dialog.resizable())), (True, True))
        for width, height in ((800, 600), (320, 240)):
            dialog.geometry(f'{width}x{height}')
            self.root.update()
            self.assertEqual((dialog.winfo_width(), dialog.winfo_height()), (width, height))
        dialog.close()

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

    def test_sync_confirmation_returns_dialog_result(self):
        """同步兼容入口仍须经统一 ConfirmDialog，而非回落系统 messagebox。"""
        self.root.after_idle(
            lambda: next(child for child in self.root.winfo_children()
                         if isinstance(child, ConfirmDialog))._confirm())
        self.assertTrue(ask_confirmation(self.root, '确认', '继续执行？'))

    @staticmethod
    def _captured_focus(dialog):
        seen = []
        for widget in dialog._descendants(dialog):
            if hasattr(widget, 'focus_set'):
                widget.focus_set = lambda widget=widget: seen.append(widget)
        dialog._focus_first_interactive()
        return seen

    def test_string_dialog_initially_focuses_its_entry(self):
        dialog = StringDialog(self.root, '命名', '输入名称')
        seen = self._captured_focus(dialog)
        self.assertEqual(seen, [dialog.entry])
        dialog.close()

    def test_notice_dialog_initially_focuses_primary_action(self):
        dialog = NoticeDialog(self.root, '完成', '已经处理完成。')
        seen = self._captured_focus(dialog)
        buttons = dialog.actions.winfo_children()
        self.assertEqual(seen, [buttons[0]])
        self.assertEqual(str(buttons[0].cget('text')), '知道了')
        dialog.close()

    def test_confirm_focus_is_primary_but_dangerous_confirm_starts_on_cancel(self):
        normal = ConfirmDialog(self.root, '确认', '继续执行？')
        normal_focus = self._captured_focus(normal)
        normal_buttons = {str(button.cget('text')): button for button in normal.actions.winfo_children()}
        self.assertEqual(normal_focus, [normal_buttons['确认']])
        normal.close()

        dangerous = ConfirmDialog(self.root, '危险操作', '确认删除？', dangerous=True)
        dangerous_focus = self._captured_focus(dangerous)
        dangerous_buttons = {str(button.cget('text')): button for button in dangerous.actions.winfo_children()}
        self.assertEqual(dangerous_focus, [dangerous_buttons['取消']])
        dangerous.close()

    def test_flyout_uses_shared_popup_surface(self):
        popup = Flyout(self.root)
        self.assertEqual(str(popup.cget('bg')).lower(), COLORS['border_default'].lower())
        self.assertEqual(str(popup.body.cget('bg')).lower(), COLORS['background_primary'].lower())
        popup.destroy()

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
