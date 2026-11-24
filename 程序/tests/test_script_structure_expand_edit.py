"""REQ-S02-37：剧本结构页改成唯一编辑器后，进入编辑不再扩张／遮盖其他内容框。

原 R2529 的「编辑时本框占满上下两行、盖住另一框」契约随双框一并删除：
现在全页只有一个内容框，进入／退出编辑时外框的 grid 位置不变，页面上也没有
expand_editing_box／restore_split_boxes 这对钩子。
"""
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

from test_ui_reading_density import _make_project, _settle, _show_script_structure  # noqa: E402


class ScriptStructureSingleBoxEditTests(unittest.TestCase):
    def _open(self, project):
        win = tk.Tk()
        win.geometry("1280x800+40+40")
        win.deiconify()
        win.update()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        desktop = _show_script_structure(win, project)
        errors = []

        def safe(fn):
            try:
                return fn()
            except ValueError as exc:
                errors.append(str(exc))
        desktop.safe = safe
        return win, desktop, errors

    def test_edit_keeps_the_single_editor_in_place(self):
        """REQ-S02-37：进入编辑后编辑器仍在原位、占满整页；退出后位置不变。"""
        with tempfile.TemporaryDirectory() as td:
            project, _writing = _make_project(td)
            win, desktop, errors = self._open(project)
            frame = desktop.script_structure_editor_box
            before = dict(frame.pack_info()) if frame.winfo_manager() == 'pack' else dict(frame.grid_info())
            session = desktop.script_structure_editor_preview_edit_session
            session.toggle_edit()
            _settle(win)
            self.assertEqual(errors, [])
            self.assertTrue(session.editing)
            after = dict(frame.pack_info()) if frame.winfo_manager() == 'pack' else dict(frame.grid_info())
            self.assertEqual(after, before, '单编辑器布局下进入编辑不得移动外框')
            session.toggle_edit()
            _settle(win)
            self.assertFalse(session.editing)
            done = dict(frame.pack_info()) if frame.winfo_manager() == 'pack' else dict(frame.grid_info())
            self.assertEqual(done, before)
            self.assertEqual(errors, [])

    def test_no_expand_hooks_left(self):
        """REQ-S02-37：expand_editing_box／restore_split_boxes 已随双框一并删除。"""
        with tempfile.TemporaryDirectory() as td:
            project, _writing = _make_project(td)
            win, desktop, errors = self._open(project)
            box = desktop.script_structure_editor_preview_content_box
            for name in ('expand_editing_box', 'restore_split_boxes'):
                self.assertFalse(hasattr(box.owner, name),
                                 name + ' 应已删除：单编辑器没有可扩张的另一半')


if __name__ == "__main__":
    unittest.main()
