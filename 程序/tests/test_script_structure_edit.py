# -*- coding: utf-8 -*-
"""REQ-S02-35/37：剧本结构页编辑会话与无 Tk 编辑控制器（R2724 反转 R1862 手动保存）。

控制器（无 Tk）：初始原文＋落盘基线＋变化判定。真 Tk（withdraw 根窗口）：
REQ-S02-37 起「编辑／删除」按钮已删，编辑入口移到文本框右键菜单首项
「编辑／退出编辑」；退出先落盘再退出、不再询问「放弃修改」；
撤销／复原／保存在同一右键菜单（见 test_script_context_menu）。
"""
import tempfile
import types
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock
from tkinter import ttk

from script_structure_edit_controller import ScriptStructureEditController
from ui_widgets import ContextMenu


class _FakeStatus:
    def set(self, text):
        self.text = text


class _FakePage:
    def __init__(self, confirm=None):
        self.status = _FakeStatus()
        self.win = None
        self.confirm = confirm or mock.Mock(return_value=True)
        created = []

        def context_menu(owner):
            menu = ContextMenu(owner)
            menu.menu.tk_popup = lambda *a, **k: None  # 只不真弹，避免阻塞
            created.append(menu)
            return menu
        self.menus = created
        self.script_page_services = types.SimpleNamespace(
            confirm=self.confirm, context_menu=context_menu)

    def safe(self, fn):
        return fn()


class ControllerTests(unittest.TestCase):
    def test_save_writes_changed_text_and_updates_baseline(self):
        """REQ-S02-35：save 落盘并更新基线；dirty 按文本与基线比较。"""
        saved = []
        controller = ScriptStructureEditController(save=saved.append)
        controller.begin_edit('原始')
        self.assertEqual(controller.initial, '原始')
        self.assertEqual(controller.saved, '原始')
        self.assertFalse(controller.dirty('原始'))
        self.assertTrue(controller.dirty('改动'))
        self.assertTrue(controller.save('改动'))
        self.assertEqual(saved, ['改动'])
        self.assertFalse(controller.dirty('改动'))
        self.assertTrue(controller.save('再改'))
        self.assertEqual(saved, ['改动', '再改'])

    def test_unchanged_save_does_not_write(self):
        """REQ-S02-35：与上次落盘相同的内容不写盘，返回 False。"""
        saved = []
        controller = ScriptStructureEditController(save=saved.append)
        controller.begin_edit('原文')
        self.assertFalse(controller.save('原文'))
        self.assertEqual(saved, [])

    def test_save_before_edit_is_rejected(self):
        controller = ScriptStructureEditController(save=lambda text: None)
        with self.assertRaises(ValueError):
            controller.save('内容')


class ScriptStructureEditSessionTests(unittest.TestCase):
    def _setup(self, kind='natural', confirm_answer=True, editable=True):
        win = tk.Tk()
        win.withdraw()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        preview = tk.Text(win, undo=True)
        preview.pack()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / 'script.md'
        target.write_text('原始内容', encoding='utf-8')
        active = {'path': str(target)}
        loaded = {'raw': '原始内容'}
        # 与真实 set_preview 一致：预览先展示已读原文并处于只读态。
        preview.insert('1.0', loaded['raw'])
        preview.edit_reset()
        preview.configure(state='disabled')
        page = _FakePage(mock.Mock(return_value=confirm_answer))
        page.win = win
        from desktop_script_edit_session import _install_script_edit_controls, _reset_preview_text
        box = types.SimpleNamespace(preview=preview, loaded=loaded, active=active, kind=kind,
                                    title='自然剧本', editable=editable, attribute='box',
                                    owner=types.SimpleNamespace())
        def set_preview(value):
            loaded['raw'] = value
            _reset_preview_text(preview, value, kind)
            preview.configure(state='disabled')
        box.set_preview = set_preview
        _install_script_edit_controls(page, box)
        win.update()  # 先让控件完成首次布局，合成事件才稳定投递
        return win, preview, page, target

    def test_no_buttons_registered_only_session_and_controller(self):
        """REQ-S02-37：会话与控制器照常登记；「编辑／删除」按钮与撤销类按钮属性均不再建。"""
        for kind in ('natural', 'structured'):
            with self.subTest(kind=kind):
                win, preview, page, target = self._setup(kind=kind)
                self.assertTrue(hasattr(page, 'box_edit_session'))
                self.assertTrue(hasattr(page, 'box_controller'))
                for removed in ('box_edit_button', 'box_delete_button',
                                'box_back_button', 'box_restore_button', 'box_save_button'):
                    self.assertFalse(hasattr(page, removed), removed + ' 应已从页面属性移除')
                session = page.box_edit_session
                self.assertFalse(hasattr(session, 'edit_button'))
                self.assertFalse(hasattr(session, 'delete_button'))
                self.assertFalse(hasattr(session, 'delete_document'),
                                 '删除已收进文件面板右键菜单（REQ-S02-37）')

    def test_begin_edit_moves_keyboard_focus_into_preview(self):
        win, preview, page, target = self._setup()
        focused = []
        preview.focus_set = lambda: focused.append(preview)
        page.box_edit_session.toggle_edit()
        self.assertEqual(focused, [preview])

    def test_exit_flushes_pending_save_without_confirm(self):
        """R2724：退出编辑先把未落盘内容写回再退出，全程不再询问「放弃修改」。"""
        win, preview, page, target = self._setup()
        session = page.box_edit_session
        session.toggle_edit()
        win.update()
        preview.insert('end', '改动')
        win.update()
        session.toggle_edit()               # 立即退出，不等 600ms 防抖
        win.update()
        self.assertEqual(target.read_text(encoding='utf-8'), '原始内容改动\n')
        self.assertEqual(str(preview.cget('state')), 'disabled')
        self.assertFalse(session.editing)
        page.confirm.assert_not_called()

    def test_exit_without_changes_keeps_source_bytes(self):
        """R2724：进入编辑后未改动就退出，不写盘、不询问。"""
        win, preview, page, target = self._setup()
        session = page.box_edit_session
        before = target.read_bytes()
        session.toggle_edit()
        win.update()
        self.assertTrue(session.editing)
        session.toggle_edit()
        win.update()
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(str(preview.cget('state')), 'disabled')
        page.confirm.assert_not_called()

    def test_readonly_box_refuses_edit(self):
        """REQ-S02-38：只读文档点「编辑」报错，不进入编辑态。"""
        win, preview, page, target = self._setup(editable=False)
        errors = []

        def safe(fn):
            try:
                return fn()
            except ValueError as exc:
                errors.append(str(exc))
        page.safe = safe
        page.safe(page.box_edit_session.toggle_edit)
        self.assertEqual(errors, ['当前没有可修改的剧本文档。'])
        self.assertEqual(str(preview.cget('state')), 'disabled')


if __name__ == '__main__':
    unittest.main()
