# -*- coding: utf-8 -*-
"""REQ-S02-35：剧本结构页「编辑／退出」按钮与无 Tk 编辑控制器（R2724 反转 R1862 手动保存）。

控制器（无 Tk）：初始原文＋落盘基线＋变化判定。真 Tk（withdraw 根窗口）：可见按钮只剩
「编辑」（结构框另有「删除」），编辑中「编辑」变「退出」；退出先落盘再退出、不再询问
「放弃修改」；撤销／复原／保存收进右键菜单（见 test_script_context_menu）。
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


class ScriptStructureEditButtonTests(unittest.TestCase):
    def _setup(self, kind='natural', confirm_answer=True, editable=True):
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
        # 合并 R1842／重构批次：入参收进内容框对象（参数个数门禁），各值不变。
        box = types.SimpleNamespace(preview=preview, loaded=loaded, active=active, kind=kind,
                                    title='自然剧本', editable=editable, attribute='box',
                                    # R2529：编辑时页面负责扩展/复原分屏；假页面只给空实现。
                                    owner=types.SimpleNamespace(
                                        expand_editing_box=lambda content: None,
                                        restore_split_boxes=lambda: None))
        def set_preview(value):
            loaded['raw'] = value
            _reset_preview_text(preview, value, kind)
            preview.configure(state='disabled')
        box.set_preview = set_preview
        box.delete_document = mock.Mock()
        self.box = box
        _install_script_edit_controls(page, controls, box)
        win.update()  # 先让控件完成首次布局，合成事件才稳定投递
        return win, preview, page, target

    def test_visible_buttons_are_only_edit_and_structured_delete(self):
        """REQ-S02-35／R2724：可见按钮只剩「编辑」（结构框另有「删除」），撤销类按钮已移除。"""
        win, preview, page, target = self._setup()
        self.assertEqual(page.box_edit_button.cget('text'), '编辑')
        self.assertEqual(list(page.box_edit_button.master.pack_slaves()),
                         [page.box_edit_button])
        for removed in ('box_back_button', 'box_restore_button', 'box_save_button'):
            self.assertFalse(hasattr(page, removed), removed + ' 应已从页面属性移除')
        win, preview, page, target = self._setup(kind='structured')
        self.assertEqual([b.cget('text') for b in
                          (page.box_edit_button, page.box_delete_button)], ['编辑', '删除'])
        self.assertEqual(list(page.box_edit_button.master.pack_slaves()),
                         [page.box_edit_button, page.box_delete_button])

    def test_exit_flushes_pending_save_without_confirm(self):
        """R2724：退出编辑先把未落盘内容写回再退出，全程不再询问「放弃修改」。"""
        win, preview, page, target = self._setup()
        page.box_edit_button.invoke()
        win.update()
        preview.insert('end', '改动')
        win.update()
        page.box_edit_button.invoke()   # 立即退出，不等 600ms 防抖
        win.update()
        self.assertEqual(target.read_text(encoding='utf-8'), '原始内容改动\n')
        self.assertEqual(str(preview.cget('state')), 'disabled')
        self.assertEqual(page.box_edit_button.cget('text'), '编辑')
        page.confirm.assert_not_called()

    def test_exit_without_changes_keeps_source_bytes(self):
        """R2724：进入编辑后未改动就退出，不写盘、不询问。"""
        win, preview, page, target = self._setup()
        before = target.read_bytes()
        page.box_edit_button.invoke()
        win.update()
        self.assertEqual(page.box_edit_button.cget('text'), '退出')
        page.box_edit_button.invoke()
        win.update()
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(str(preview.cget('state')), 'disabled')
        page.confirm.assert_not_called()

    def test_editing_state_disables_structured_delete(self):
        """R1864／R2724：结构剧本框「删除」只在非编辑态可用；确认后才删。"""
        win, preview, page, target = self._setup(kind='structured', confirm_answer=False)
        self.assertFalse(page.box_delete_button.instate(['disabled']))
        page.box_edit_button.invoke()
        win.update()
        self.assertTrue(page.box_delete_button.instate(['disabled']), '编辑中不能删除')
        page.box_edit_button.invoke()
        win.update()
        page.box_delete_button.invoke()
        self.assertEqual(page.confirm.call_args.kwargs.get('dangerous'), True)
        self.box.delete_document.assert_not_called()
        page.confirm.return_value = True
        page.box_delete_button.invoke()
        self.box.delete_document.assert_called_once_with()

    def test_natural_box_has_no_delete(self):
        win, preview, page, target = self._setup()
        self.assertFalse(hasattr(page, 'box_delete_button'))

    def test_readonly_box_refuses_edit(self):
        """只读文档点「编辑」报错，不进入编辑态。"""
        win, preview, page, target = self._setup(editable=False)
        errors = []

        def safe(fn):
            try:
                return fn()
            except ValueError as exc:
                errors.append(str(exc))
        page.safe = safe
        page.box_edit_button.invoke()
        self.assertEqual(errors, ['当前没有可修改的剧本文档。'])
        self.assertEqual(str(preview.cget('state')), 'disabled')


if __name__ == '__main__':
    unittest.main()
