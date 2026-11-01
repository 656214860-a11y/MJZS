"""R2168：剧本结构页的内容框里没有文档时，「编辑」禁用，点了也不报错。

用户诊断记录里「当前没有可修改的剧本文档。」九天出现 26 次：还没生成结构剧本（或还没有
自然剧本）时，对应内容框的「编辑」仍可点，点了只得到这句报错。框里有文档时照常可编辑。
"""
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

from test_ui_reading_density import _show_script_structure  # noqa: E402

NATURAL = "第 1 集\n\n场景 1：旧站台\n\n阿远：我回来了。\n"
BOXES = ("script_structure_source_preview", "script_structure_output_preview")


class EmptyScriptBoxEditTests(unittest.TestCase):
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

    def test_structured_box_without_document_disables_edit(self):
        """有自然剧本、还没有结构剧本：自然剧本框可编辑，结构剧本框「编辑」禁用且点了不报错。"""
        with tempfile.TemporaryDirectory() as td:
            writing = Path(td) / "project" / "writing"
            writing.mkdir(parents=True)
            (writing / "剧本_甲.md").write_text(NATURAL, encoding="utf-8")
            win, desktop, errors = self._open(writing.parent)
            self.assertFalse(desktop.script_structure_source_preview_edit_button.instate(["disabled"]),
                             "自然剧本框里有文档，「编辑」应可用")
            button = desktop.script_structure_output_preview_edit_button
            self.assertTrue(button.instate(["disabled"]), "还没有结构剧本时「编辑」应禁用")
            button.invoke()
            win.update()
            self.assertEqual(errors, [])
            self.assertEqual(button.cget("text"), "编辑")
            self.assertEqual(str(desktop.script_structure_output_preview.cget("state")), "disabled")

    def test_empty_project_disables_both_edit_buttons(self):
        """两份剧本都没有：两个框的「编辑」都禁用，点了都不报错。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            project.mkdir()
            win, desktop, errors = self._open(project)
            for name in BOXES:
                button = getattr(desktop, name + "_edit_button")
                self.assertTrue(button.instate(["disabled"]), name + "：框里没有文档时「编辑」应禁用")
                button.invoke()
                win.update()
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
