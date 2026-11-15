# -*- coding: utf-8 -*-
"""REQ-S02-35：Ctrl+Z／Ctrl+Y·Ctrl+Shift+Z 编辑撤销快捷键（R2724）。

真 Tk（withdraw 根窗口）＋ ``ShortcutRegistry``：快捷键经 registry 登记且真实绑到
文本框上（生产代码不直绑）；编辑态后退／前进走 Tk 原生 ``edit_undo``／``edit_redo``
并触发防抖自动保存，非编辑态不动文本。

隐藏桌面上 ``event_generate`` 合成不了字母键事件（实测 KeyPress 不投递），因此键位
投递由 Tk 负责、这里断言登记面与处理入口行为：registry 记录、控件绑定串、以及
``_shortcut_undo``／``_shortcut_redo`` 处理函数本身。
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

from ui_shortcuts import ShortcutRegistry  # noqa: E402


class _FakeStatus:
    def set(self, text):
        self.text = text


class _FakePage:
    def __init__(self, confirm=None):
        self.status = _FakeStatus()
        self.win = None
        self.confirm = confirm or mock.Mock(return_value=True)
        self.shortcuts = ShortcutRegistry()
        self.script_page_services = types.SimpleNamespace(
            confirm=self.confirm,
            context_menu=lambda owner: (_ for _ in ()).throw(AssertionError('不应弹菜单')))

    def safe(self, fn):
        return fn()


class ScriptUndoShortcutTests(unittest.TestCase):
    def _setup(self, kind='natural'):
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
        page = _FakePage()
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

    def test_shortcuts_registered_via_registry_and_bound_on_widget(self):
        """REQ-S02-35：Ctrl+Z 后退一步、Ctrl+Y／Ctrl+Shift+Z 前进一步，登记在 registry 并绑到文本框。"""
        win, preview, page, target, session = self._setup()
        records = [r for r in page.shortcuts.registered()
                   if r['scope'] == '剧本结构页·自然剧本']
        self.assertEqual({r['name'] for r in records}, {'后退一步', '前进一步'})
        sequences = {s.lower() for r in records for s in r['sequences']}
        self.assertIn('<control-z>', sequences)
        self.assertIn('<control-shift-z>', sequences)
        # registry 之外还要真的绑到文本框上：bind 查询返回非空绑定脚本。
        self.assertTrue(preview.bind('<Control-z>'))
        self.assertTrue(preview.bind('<Control-Shift-Z>'))
        self.assertTrue(preview.bind('<Control-y>'))

    def test_shortcut_handlers_undo_and_redo_step_by_step(self):
        """编辑态快捷键处理入口逐步后退／前进，内容与 Tk 原生撤销栈一致。"""
        win, preview, page, target, session = self._setup(kind='structured')
        page.box_edit_button.invoke()
        win.update()
        preview.insert('end', '改')
        preview.edit_separator()            # 强制分成两步撤销
        preview.insert('end', '动')
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容改动')
        session._shortcut_undo()            # Ctrl+Z 的处理入口
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容改')
        session._shortcut_undo()
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容')
        session._shortcut_redo()            # Ctrl+Shift+Z 的处理入口
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容改')
        session._shortcut_redo()            # Ctrl+Y 同一路径
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容改动')
        self.assertIsNotNone(session.pending, '撤销／重做后应照常安排防抖自动保存')

    def test_shortcut_handlers_do_nothing_when_not_editing(self):
        """非编辑态快捷键处理入口不动文本、不安排自动保存。"""
        win, preview, page, target, session = self._setup(kind='structured')
        session._shortcut_undo()
        session._shortcut_redo()
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容')
        self.assertIsNone(session.pending)
        self.assertEqual(target.read_text(encoding='utf-8'), '原始内容')


if __name__ == '__main__':
    unittest.main()
