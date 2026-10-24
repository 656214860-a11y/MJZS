"""R1958：剧本结构页「自然剧本」的编辑按钮不受“采用”状态限制。

采用记录带内容哈希，改过一次就失效；多份候选未采用时来源也为空。两种情况下
编辑按钮都应能进入编辑态，而不是报“当前没有可修改的剧本文档”。
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


class NaturalScriptEditTests(unittest.TestCase):
    def _project(self, td, names):
        project = Path(td) / "project"
        writing = project / "writing"
        writing.mkdir(parents=True)
        for name in names:
            # 正文各不相同：候选列表按内容指纹去重。
            (writing / name).write_text(NATURAL + "阿远：" + name + "。\n", encoding="utf-8")
        return project, writing

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

    def _assert_editable(self, win, desktop, errors):
        desktop.script_structure_source_preview_edit_button.invoke()
        win.update()
        self.assertEqual(errors, [])
        self.assertEqual(str(desktop.script_structure_source_preview.cget("state")), "normal")
        self.assertEqual(desktop.script_structure_source_preview_edit_button.cget("text"), "退出")

    def test_unadopted_candidate_is_editable(self):
        import script_contract
        with tempfile.TemporaryDirectory() as td:
            project, _ = self._project(td, ["剧本_甲.md", "剧本_乙.md"])
            self.assertIsNone(script_contract.resolve_script_source(project), "前提：多份候选未采用")
            win, desktop, errors = self._open(project)
            self._assert_editable(win, desktop, errors)

    def test_adopted_script_stays_editable_after_saved_edit(self):
        import script_contract
        from stage_execution_service import adopt_natural_script
        with tempfile.TemporaryDirectory() as td:
            project, writing = self._project(td, ["剧本_甲.md", "剧本_乙.md"])
            adopt_natural_script(project, writing / "剧本_甲.md")
            win, desktop, errors = self._open(project)
            self._assert_editable(win, desktop, errors)
            desktop.script_structure_source_preview.insert("end", "\n阿远：再见。")
            win.update()
            desktop.script_structure_source_preview_save_button.invoke()
            win.update()
            self.assertEqual(errors, [])
            self.assertIn("再见", (writing / "剧本_甲.md").read_text(encoding="utf-8"))
            self.assertIn("采用选中剧本", desktop.status.get())
            self.assertIsNone(script_contract.resolve_script_source(project), "前提：改后采用记录失效")

            # 重新进入本页（内容变了，页面按签名重建）后再点编辑，仍应可编辑（修复前此处报错）。
            import pet_state
            before = desktop.script_structure_source_preview_edit_button
            desktop.show(pet_state.PAGE_OF["script_structure"])
            win.update()
            self.assertIsNot(desktop.script_structure_source_preview_edit_button, before, "页面应已重建")
            self._assert_editable(win, desktop, errors)


if __name__ == "__main__":
    unittest.main()
