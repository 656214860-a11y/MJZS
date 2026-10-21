# -*- coding: utf-8 -*-
"""REQ-S02-35：剧本结构页「编辑／后退／恢复」按钮与无 Tk 编辑控制器。

控制器（无 Tk）：内容快照撤销栈 + 防抖自动保存调度。真 Tk（withdraw 根窗口）：按钮
文本、编辑后防抖落盘、两次编辑后「后退」逐级回到最初内容并落盘、无可后退时禁用。
"""
import tempfile
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
        """REQ-S02-35：两次编辑后后退一次回到第一次编辑，再退回到原始并禁用。"""
        saved = []
        controller = ScriptStructureEditController(save=saved.append, debounce_ms=0)
        controller.begin_edit('原始')
        controller.record_edit('第一次编辑')
        controller.record_edit('第二次编辑')
        self.assertEqual(saved, ['第一次编辑', '第二次编辑'])
        self.assertTrue(controller.can_undo)
        self.assertEqual(controller.undo(), '第一次编辑')
        self.assertEqual(controller.undo(), '原始')
        self.assertFalse(controller.can_undo)
        with self.assertRaises(ValueError):
            controller.undo()

    def test_unchanged_edit_does_not_push_or_save(self):
        saved = []
        controller = ScriptStructureEditController(save=saved.append, debounce_ms=0)
        controller.begin_edit('原文')
        self.assertFalse(controller.record_edit('原文'))
        self.assertFalse(controller.can_undo)
        self.assertEqual(saved, [])

    def test_debounce_schedules_one_save_and_flushes_on_fire(self):
        saved = []
        pending = {}

        def schedule(delay, callback):
            pending['delay'] = delay
            pending['callback'] = callback
            return 'handle'

        def cancel(handle):
            pending['cancelled'] = handle

        controller = ScriptStructureEditController(
            save=saved.append, debounce_ms=600, schedule=schedule, cancel=cancel)
        controller.begin_edit('初始')
        controller.record_edit('改动')
        self.assertEqual(saved, [], '防抖未触发前不得落盘')
        self.assertTrue(controller.pending_save)
        self.assertEqual(pending['delay'], 600)
        pending['callback']()
        self.assertEqual(saved, ['改动'])
        self.assertFalse(controller.pending_save)

    def test_undo_cancels_pending_debounce_and_saves_immediately(self):
        saved = []
        scheduled = []

        def schedule(delay, callback):
            scheduled.append(callback)
            return len(scheduled)

        def cancel(handle):
            pass

        controller = ScriptStructureEditController(
            save=saved.append, debounce_ms=600, schedule=schedule, cancel=cancel)
        controller.begin_edit('原始')
        controller.record_edit('改动')
        self.assertEqual(len(scheduled), 1, '应安排一次防抖保存')
        self.assertEqual(controller.undo(), '原始')
        self.assertIn('原始', saved)


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
        _install_script_edit_controls(page, controls, preview, loaded, active, kind,
                                      '自然剧本', True, 'box')
        return win, preview, page, target

    def test_buttons_are_edit_back_restore_and_no_save(self):
        """REQ-S02-35：按钮文本恰为「编辑」「后退」「恢复」，无「保存修改」。"""
        win, preview, page, target = self._setup()
        self.assertEqual(page.box_edit_button.cget('text'), '编辑')
        self.assertEqual(page.box_back_button.cget('text'), '后退')
        self.assertEqual(page.box_restore_button.cget('text'), '恢复')
        self.assertFalse(hasattr(page, 'box_save_button'), '不应再有保存修改按钮')

    def test_edit_auto_saves_and_back_walks_to_original(self):
        """REQ-S02-35：编辑后落盘；两次编辑后后退一次回第一次、再退回到原始，后退禁用。"""
        win, preview, page, target = self._setup()
        controller = page.box_controller
        page.box_edit_button.invoke()
        win.update()
        self.assertEqual(str(preview.cget('state')), 'normal')

        preview.insert('end', '第一次')
        win.update()
        controller.save_now()
        self.assertEqual(target.read_text(encoding='utf-8').strip(), '原始内容第一次')

        preview.insert('end', '第二次')
        win.update()
        controller.save_now()
        self.assertEqual(target.read_text(encoding='utf-8').strip(), '原始内容第一次第二次')

        page.box_back_button.invoke()
        win.update()
        self.assertEqual(target.read_text(encoding='utf-8').strip(), '原始内容第一次')

        page.box_back_button.invoke()
        win.update()
        self.assertEqual(target.read_text(encoding='utf-8').strip(), '原始内容')
        self.assertTrue(page.box_back_button.instate(['disabled']), '无可后退时后退按钮应禁用')


if __name__ == '__main__':
    unittest.main()
