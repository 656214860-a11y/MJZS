"""R2529：剧本结构页进入编辑时内容框扩展到整页，退出编辑自动复原。

点上方「自然剧本」的编辑：本框向下扩大盖住结构剧本框；
点下方「结构剧本」的编辑：本框向上扩大盖住自然剧本框；退出编辑两框回到各占一半。
"""
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

from test_ui_reading_density import _make_project, _settle, _show_script_structure  # noqa: E402


class ScriptStructureExpandEditTests(unittest.TestCase):
    def _project_with_both(self, td):
        project, writing = _make_project(td)
        structured = writing / "结构剧本"
        structured.mkdir()
        (structured / "script0.md").write_text(
            "# 结构化剧本\n\n## 分场剧本\n\n正文\n", encoding="utf-8")
        return project

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

    def _assert_expanded(self, editing, hidden):
        info = editing.grid_info()
        self.assertEqual(int(info.get('row')), 0, '编辑框应从第一行起占')
        self.assertEqual(int(info.get('rowspan')), 2, '编辑框应占满上下两行')
        self.assertEqual(hidden.winfo_manager(), '', '另一个内容框应被盖住（不在布局中）')

    def _assert_restored(self, desktop):
        for frame, row in ((desktop.script_structure_source_box, 0),
                           (desktop.script_structure_output_box, 1)):
            self.assertEqual(frame.winfo_manager(), 'grid')
            info = frame.grid_info()
            self.assertEqual(int(info.get('row')), row)
            self.assertEqual(int(info.get('rowspan')), 1)

    def test_natural_edit_expands_down_and_exit_restores(self):
        with tempfile.TemporaryDirectory() as td:
            win, desktop, errors = self._open(self._project_with_both(td))
            source, output = desktop.script_structure_source_box, desktop.script_structure_output_box
            before = output.winfo_height()
            desktop.script_structure_source_preview_edit_button.invoke()
            _settle(win)
            self.assertEqual(errors, [])
            self._assert_expanded(source, output)
            self.assertGreater(source.winfo_height(), int(before * 1.5),
                               '自然剧本框编辑时应拿到结构剧本框的高度')
            # 自动保存／立即保存都不退出编辑（R2724 契约），框保持扩展；「退出」才复原。
            desktop.script_structure_source_preview.insert('end', '\n阿远：再见。')
            win.update()
            desktop.script_structure_source_preview_edit_session.save_now()
            win.update()
            self.assertEqual(int(source.grid_info().get('rowspan')), 2, '保存后仍在编辑态，保持扩展')
            desktop.script_structure_source_preview_edit_button.invoke()
            _settle(win)
            self._assert_restored(desktop)
            self.assertEqual(errors, [])

    def test_structured_edit_expands_up_and_exit_restores(self):
        with tempfile.TemporaryDirectory() as td:
            win, desktop, errors = self._open(self._project_with_both(td))
            source, output = desktop.script_structure_source_box, desktop.script_structure_output_box
            before = source.winfo_height()
            desktop.script_structure_output_preview_edit_button.invoke()
            _settle(win)
            self.assertEqual(errors, [])
            self._assert_expanded(output, source)
            self.assertGreater(output.winfo_height(), int(before * 1.5),
                               '结构剧本框编辑时应向上吃掉自然剧本框的高度')
            desktop.script_structure_output_preview_edit_button.invoke()
            _settle(win)
            self._assert_restored(desktop)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
