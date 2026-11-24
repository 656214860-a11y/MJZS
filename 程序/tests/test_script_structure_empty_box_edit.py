"""REQ-S02-37/38：唯一编辑器没有可编辑文档或显示只读文档时，「编辑」不可用、点了不进入编辑态。

用户诊断记录里「当前没有可修改的剧本文档。」曾九天出现 26 次：REQ-S02-37 起按钮删除，
编辑入口移到右键菜单首项，无可编辑文档时该菜单项直接禁用；经 ``toggle_edit`` 入口
调用仍报同一句错误。框里有可编辑文档时照常进入编辑态。
"""
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

from test_ui_reading_density import _show_script_structure  # noqa: E402
from ui_widgets import ContextMenu  # noqa: E402

NATURAL = "第 1 集\n\n场景 1：旧站台\n\n阿远：我回来了。\n"


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

    def test_editor_without_document_refuses_edit(self):
        """空项目：编辑器无可编辑文档，toggle_edit 报错且不进入编辑态。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            project.mkdir()
            win, desktop, errors = self._open(project)
            session = desktop.script_structure_editor_preview_edit_session
            desktop.safe(session.toggle_edit)
            win.update()
            self.assertEqual(errors, ['当前没有可修改的剧本文档。'])
            self.assertFalse(session.editing)
            self.assertEqual(str(desktop.script_structure_editor_preview.cget("state")), "disabled")

    def test_edit_menu_item_disabled_without_document(self):
        """空项目：右键菜单仍弹出，首项「编辑」与其余四项全部禁用。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            project.mkdir()
            win, desktop, errors = self._open(project)
            preview = desktop.script_structure_editor_preview
            # 隐藏桌面上 tk_popup 会真弹并卡住事件循环：打桩弹出时机，菜单本体照常构建。
            with mock.patch.object(ContextMenu, 'popup', lambda self, event: 'break'):
                preview.event_generate('<Button-3>', x=5, y=5)
            win.update()
            menu = desktop.script_structure_editor_preview_edit_session.last_menu.menu
            end = menu.index('end')
            labels = [menu.entrycget(i, 'label') for i in range(end + 1)]
            states = [menu.entrycget(i, 'state') for i in range(end + 1)]
            self.assertEqual(labels, ['编辑', '后退一步', '前进一步', '复原全文', '立即保存'])
            self.assertEqual(states, ['disabled'] * 5)

    def test_editor_with_document_enters_edit(self):
        """有可编辑文档：toggle_edit 进入编辑态，预览转 normal。"""
        with tempfile.TemporaryDirectory() as td:
            writing = Path(td) / "project" / "writing"
            writing.mkdir(parents=True)
            (writing / "剧本_甲.md").write_text(NATURAL, encoding="utf-8")
            win, desktop, errors = self._open(writing.parent)
            box = desktop.script_structure_editor_preview_content_box
            box.select_document(writing / "剧本_甲.md")
            win.update()
            session = desktop.script_structure_editor_preview_edit_session
            session.toggle_edit()
            win.update()
            self.assertEqual(errors, [])
            self.assertTrue(session.editing)
            self.assertEqual(str(desktop.script_structure_editor_preview.cget("state")), "normal")


if __name__ == "__main__":
    unittest.main()
