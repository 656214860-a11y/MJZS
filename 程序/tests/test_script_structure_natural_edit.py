"""R1958／REQ-S02-38：剧本结构页的自然剧本可编辑性不受“采用”状态限制。

采用记录带内容哈希，改过一次就失效；多份候选未采用时来源也为空。两种情况下
该文档经面板点选显示后都应能进入编辑态（REQ-S02-37 起入口为右键菜单「编辑」），
而不是报“当前没有可修改的剧本文档”。
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
        session = desktop.script_structure_editor_preview_edit_session
        session.toggle_edit()
        win.update()
        self.assertEqual(errors, [])
        self.assertTrue(session.editing)
        self.assertEqual(str(desktop.script_structure_editor_preview.cget("state")), "normal")

    def test_unadopted_candidate_is_editable(self):
        import script_contract
        with tempfile.TemporaryDirectory() as td:
            project, writing = self._project(td, ["剧本_甲.md", "剧本_乙.md"])
            self.assertIsNone(script_contract.resolve_script_source(project), "前提：多份候选未采用")
            win, desktop, errors = self._open(project)
            box = desktop.script_structure_editor_preview_content_box
            box.select_document(writing / "剧本_甲.md")
            win.update()
            self._assert_editable(win, desktop, errors)

    def test_adopted_script_stays_editable_after_saved_edit(self):
        import script_contract
        from stage_execution_service import adopt_natural_script
        with tempfile.TemporaryDirectory() as td:
            project, writing = self._project(td, ["剧本_甲.md", "剧本_乙.md"])
            adopt_natural_script(project, writing / "剧本_甲.md")
            win, desktop, errors = self._open(project)
            box = desktop.script_structure_editor_preview_content_box
            self.assertEqual(box.active['path'], (writing / "剧本_甲.md").resolve(),
                             "默认文档应是采用的自然剧本")
            self._assert_editable(win, desktop, errors)
            desktop.script_structure_editor_preview.insert("end", "\n阿远：再见。")
            win.update()
            desktop.script_structure_editor_preview_edit_session.save_now()
            win.update()
            self.assertEqual(errors, [])
            self.assertIn("再见", (writing / "剧本_甲.md").read_text(encoding="utf-8"))
            self.assertIn("重新采用", desktop.status.get(),
                          "保存后应提示采用记录已失效（REQ-S02-41 提示改写）")
            self.assertIsNone(script_contract.resolve_script_source(project), "前提：改后采用记录失效")

            # 重新进入本页（内容变了，页面按签名重建）后再点编辑，仍应可编辑（修复前此处报错）。
            import infra.pet_state as pet_state
            before = desktop.script_structure_editor_preview_edit_session
            desktop.show(pet_state.PAGE_OF["script_structure"])
            win.update()
            self.assertIsNot(desktop.script_structure_editor_preview_edit_session, before, "页面应已重建")
            box = desktop.script_structure_editor_preview_content_box
            box.select_document(writing / "剧本_甲.md")
            win.update()
            self._assert_editable(win, desktop, errors)


if __name__ == "__main__":
    unittest.main()
