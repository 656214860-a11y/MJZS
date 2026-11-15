# -*- coding: utf-8 -*-
"""REQ-S02-35：剧本结构页文本框右键菜单（R2724）。

真 Tk（withdraw 根窗口）：右键菜单四项顺序「后退一步／前进一步／复原全文／立即保存」，
经 ``ContextMenu`` 构建；后退／前进走 Tk 原生 ``edit_undo``／``edit_redo`` 并触发防抖
自动保存；「复原全文」先确认、取消不动；「立即保存」幂等；非编辑态四项禁用。
"""
import sys
import tempfile
import tkinter as tk
import types
import unittest
from pathlib import Path
from unittest import mock
from tkinter import ttk

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

import agent.core  # noqa: E402
from ui_widgets import ContextMenu  # noqa: E402


class _FakeStatus:
    def set(self, text):
        self.text = text


class _FakePage:
    def __init__(self, confirm=None):
        self.status = _FakeStatus()
        self.win = None
        self.confirm = confirm or mock.Mock(return_value=True)
        self.menus = []

        def context_menu(owner):
            menu = ContextMenu(owner)
            menu.menu.tk_popup = lambda *a, **k: None  # 只不真弹，避免阻塞
            self.menus.append(menu)
            return menu
        self.script_page_services = types.SimpleNamespace(
            confirm=self.confirm, context_menu=context_menu)

    def safe(self, fn):
        return fn()


def _labels(menu):
    return [menu.menu.entrycget(i, 'label') for i in range(menu.menu.index('end') + 1)]


def _states(menu):
    return [menu.menu.entrycget(i, 'state') for i in range(menu.menu.index('end') + 1)]


class ScriptContextMenuTests(unittest.TestCase):
    def _setup(self, kind='natural', confirm_answer=True):
        win = tk.Tk()
        win.withdraw()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        controls = ttk.Frame(win)
        controls.pack()
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
        box = types.SimpleNamespace(
            preview=preview, loaded=loaded, active=active, kind=kind,
            title='自然剧本' if kind == 'natural' else '结构剧本',
            editable=True, attribute='box',
            owner=types.SimpleNamespace(
                expand_editing_box=lambda content_: None,
                restore_split_boxes=lambda: None))

        def set_preview(value):
            loaded['raw'] = value
            _reset_preview_text(preview, value, kind)
            preview.configure(state='disabled')
        box.set_preview = set_preview
        box.delete_document = mock.Mock()
        _install_script_edit_controls(page, controls, box)
        win.update()  # 先让控件完成首次布局，合成事件才稳定投递
        return win, preview, page, target, page.box_edit_session

    def _right_click(self, win, preview):
        preview.event_generate('<Button-3>', x=5, y=5)
        win.update()

    def test_menu_items_order_and_enabled_after_change(self):
        """REQ-S02-35：编辑态右键菜单四项顺序固定，有改动时全部可用。"""
        win, preview, page, target, session = self._setup()
        page.box_edit_button.invoke()
        win.update()
        preview.insert('end', '改')
        win.update()
        self._right_click(win, preview)
        self.assertEqual(len(page.menus), 1)
        menu = page.menus[-1]
        self.assertIsInstance(menu, ContextMenu, '菜单必须经 ContextMenu 构建')
        self.assertEqual(_labels(menu), ['后退一步', '前进一步', '复原全文', '立即保存'])
        self.assertEqual(_states(menu), ['normal'] * 4)

    def test_menu_items_disabled_when_not_editing(self):
        """REQ-S02-35：非编辑态右键仍弹菜单，四项均禁用。"""
        win, preview, page, target, session = self._setup()
        self._right_click(win, preview)
        menu = page.menus[-1]
        self.assertEqual(_labels(menu), ['后退一步', '前进一步', '复原全文', '立即保存'])
        self.assertEqual(_states(menu), ['disabled'] * 4)

    def test_restore_full_asks_confirm_then_restores_and_saves(self):
        """「复原全文」先确认；取消不动，确认后恢复初始原文并立即落盘。"""
        win, preview, page, target, session = self._setup(kind='structured',
                                                         confirm_answer=False)
        page.box_edit_button.invoke()
        win.update()
        preview.insert('end', '全部改动')
        win.update()
        session.save_now()                  # 先把改动落盘，证明复原会写回
        self.assertIn('全部改动', target.read_text(encoding='utf-8'))
        self._right_click(win, preview)
        menu = page.menus[-1]
        menu.menu.invoke(2)                 # 复原全文
        win.update()
        call = page.confirm.call_args
        self.assertEqual(call.args[1], '复原全文')
        self.assertTrue(call.kwargs.get('dangerous'))
        self.assertIn('全部改动', preview.get('1.0', 'end-1c'), '取消后内容不变')
        self.assertIn('全部改动', target.read_text(encoding='utf-8'), '取消后不写盘')
        page.confirm.return_value = True
        menu.menu.invoke(2)
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容')
        self.assertEqual(target.read_text(encoding='utf-8'), '原始内容\n',
                         '复原后应把初始原文写回文件')
        self.assertIn('复原', page.status.text)

    def test_restore_full_disabled_without_changes(self):
        """进入编辑后未改动：「复原全文」禁用（无可复原的修改）。"""
        win, preview, page, target, session = self._setup()
        page.box_edit_button.invoke()
        win.update()
        self._right_click(win, preview)
        menu = page.menus[-1]
        self.assertEqual(_states(menu)[2], 'disabled')
        self.assertEqual(_states(menu)[0], 'normal')
        self.assertEqual(_states(menu)[1], 'normal')
        self.assertEqual(_states(menu)[3], 'normal')

    def test_undo_redo_menu_commands_walk_native_stack(self):
        """「后退一步」调 edit_undo、「前进一步」调 edit_redo，各退一步。"""
        win, preview, page, target, session = self._setup(kind='structured')
        page.box_edit_button.invoke()
        win.update()
        preview.insert('end', '改动')
        win.update()
        self._right_click(win, preview)
        menu = page.menus[-1]
        menu.menu.invoke(0)                 # 后退一步
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容')
        menu.menu.invoke(1)                 # 前进一步
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容改动')

    def test_immediate_save_menu_command_is_idempotent(self):
        """「立即保存」幂等：重复触发只写盘一次，第二次提示无变化。"""
        with mock.patch('agent.core.save_text', wraps=agent.core.save_text) as spy:
            win, preview, page, target, session = self._setup(kind='structured')
            page.box_edit_button.invoke()
            win.update()
            preview.insert('end', '保存')
            win.update()
            self._right_click(win, preview)
            menu = page.menus[-1]
            menu.menu.invoke(3)             # 立即保存
            win.update()
            menu.menu.invoke(3)             # 再点一次
            win.update()
            self.assertEqual(spy.call_count, 1)
            self.assertIn('保存', target.read_text(encoding='utf-8'))
            self.assertIn('没有变化', page.status.text)


if __name__ == '__main__':
    unittest.main()
