# -*- coding: utf-8 -*-
"""REQ-S02-35：剧本结构页「编辑／后退／恢复／保存」按钮与无 Tk 编辑控制器。

控制器（无 Tk）：内容快照撤销栈 + 手动保存（R1862 取消自动保存）。真 Tk（withdraw 根窗口）：
按钮文本与顺序、编辑与后退都不落盘、点「保存」才落盘、无可后退时禁用。
"""
import tempfile
import types
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

from script_structure_edit_controller import ScriptStructureEditController


class _FakeStatus:
    def set(self, text):
        self.text = text


class _FakePage:
    def __init__(self):
        self.status = _FakeStatus()

    def safe(self, fn):
        return fn()


class ControllerTests(unittest.TestCase):
    def test_record_edit_pushes_prior_state_and_undo_walks_back(self):
        """REQ-S02-35：两次编辑后后退一次回到第一次编辑，再退回到原始并禁用；全程不落盘。"""
        saved = []
        controller = ScriptStructureEditController(save=saved.append)
        controller.begin_edit('原始')
        controller.record_edit('第一次编辑')
        controller.record_edit('第二次编辑')
        self.assertEqual(saved, [], 'R1862：取消自动保存，编辑不落盘')
        self.assertTrue(controller.can_undo)
        self.assertEqual(controller.undo(), '第一次编辑')
        self.assertEqual(controller.undo(), '原始')
        self.assertFalse(controller.can_undo)
        self.assertEqual(saved, [], '后退也不落盘')
        with self.assertRaises(ValueError):
            controller.undo()

    def test_unchanged_edit_does_not_push_or_mark_dirty(self):
        saved = []
        controller = ScriptStructureEditController(save=saved.append)
        controller.begin_edit('原文')
        self.assertFalse(controller.record_edit('原文'))
        self.assertFalse(controller.can_undo)
        self.assertFalse(controller.dirty)
        self.assertEqual(saved, [])

    def test_save_now_writes_current_and_clears_dirty(self):
        saved = []
        controller = ScriptStructureEditController(save=saved.append)
        controller.begin_edit('初始')
        controller.record_edit('改动')
        self.assertTrue(controller.dirty)
        controller.save_now()
        self.assertEqual(saved, ['改动'])
        self.assertFalse(controller.dirty)
        controller.undo()
        self.assertTrue(controller.dirty, '后退到与已保存内容不同的版本，应提示未保存')

    def test_save_before_edit_is_rejected(self):
        controller = ScriptStructureEditController(save=lambda text: None)
        with self.assertRaises(ValueError):
            controller.save_now()


class ScriptStructureEditButtonTests(unittest.TestCase):
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
        page = _FakePage()
        from desktop_script_pages import _install_script_edit_controls
        # 合并 R1842／重构批次：入参收进内容框对象（参数个数门禁），各值不变。
        box = types.SimpleNamespace(preview=preview, loaded=loaded, active=active, kind=kind,
                                    title='自然剧本', editable=True, attribute='box')
        _install_script_edit_controls(page, controls, box)
        return win, preview, page, target

    def test_buttons_are_edit_back_restore_save(self):
        """REQ-S02-35／R1862：按钮依次为「编辑」「后退」「恢复」「保存」，保存在恢复右侧。"""
        win, preview, page, target = self._setup()
        buttons = [page.box_edit_button, page.box_back_button, page.box_restore_button, page.box_save_button]
        self.assertEqual([b.cget('text') for b in buttons], ['编辑', '后退', '恢复', '保存'])
        self.assertEqual(list(buttons[0].master.pack_slaves()), buttons)
        self.assertTrue(page.box_save_button.instate(['disabled']), '未编辑时保存禁用')

    def test_edit_saves_only_on_save_and_back_walks_to_original(self):
        """REQ-S02-35／R1862：编辑不自动落盘；点保存才落盘；后退逐级回到原始，后退禁用。"""
        win, preview, page, target = self._setup()
        page.box_edit_button.invoke()
        win.update()
        self.assertEqual(str(preview.cget('state')), 'normal')

        preview.insert('end', '第一次')
        win.update()
        self.assertEqual(target.read_text(encoding='utf-8').strip(), '原始内容', '编辑后不得自动保存')
        self.assertFalse(page.box_save_button.instate(['disabled']), '有改动时保存可点')
        page.box_save_button.invoke()
        win.update()
        self.assertEqual(target.read_text(encoding='utf-8').strip(), '原始内容第一次')
        self.assertTrue(page.box_save_button.instate(['disabled']), '保存后无改动，保存禁用')

        preview.insert('end', '第二次')
        win.update()
        page.box_back_button.invoke()
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c').strip(), '原始内容第一次')
        self.assertEqual(target.read_text(encoding='utf-8').strip(), '原始内容第一次', '后退不落盘')

        page.box_back_button.invoke()
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c').strip(), '原始内容')
        self.assertTrue(page.box_back_button.instate(['disabled']), '无可后退时后退按钮应禁用')
        page.box_save_button.invoke()
        win.update()
        self.assertEqual(target.read_text(encoding='utf-8').strip(), '原始内容')


if __name__ == '__main__':
    unittest.main()
