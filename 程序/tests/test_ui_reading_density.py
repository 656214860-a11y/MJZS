"""REQ-S02-32：技能说明与剧本正文的紧凑阅读布局。

展示层折叠整行空白，但编辑、保存和源文件字节保持不变；剧本目录按文件数
收紧，把主要宽高留给正文。
"""
import tempfile
import time
import tkinter as tk
import tkinter.font as tkfont
import unittest
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

import infra.pet_state as pet_state
import skill_note_render
from orchestrator import skill_notes
import ui_tokens


def _settle(widget, iterations=10):
    for _ in range(iterations):
        widget.update_idletasks()
        widget.update()
        time.sleep(0.03)


def _has_blank_line_outside_code(fragments):
    previous_newline = False
    for text, tags in fragments:
        if skill_note_render.CODE_BLOCK in tags:
            previous_newline = False
            continue
        for char in text:
            if char == "\n":
                if previous_newline:
                    return True
                previous_newline = True
            else:
                previous_newline = False
    return False


def _make_project(td):
    project = Path(td) / "project"
    writing = project / "writing"
    writing.mkdir(parents=True)
    (writing / "script_raw.md").write_text(
        "第 1 集\n\n场景 1：旧站台\n\n阿远：我回来了。\n",
        encoding="utf-8",
    )
    return project, writing


def _show_script_structure(win, project):
    import desktop as desktop_module

    original = desktop_module.Desktop.choose_project
    desktop_module.Desktop.choose_project = lambda self: None
    try:
        desktop = desktop_module.Desktop(win, root=PROGRAM)
    finally:
        desktop_module.Desktop.choose_project = original
    desktop.root = project
    desktop.show(pet_state.PAGE_OF["script_structure"])
    _settle(win)
    return desktop


class SkillNoteDensityTests(unittest.TestCase):
    def test_all_registered_stage_skills_render_without_display_blank_lines(self):
        """REQ-S02-32：展示副本不得用整行空白分隔普通内容。"""
        files = sorted((PROGRAM / "skills").glob("*/*.skill.md"))
        self.assertGreaterEqual(len(files), 13)
        sources_with_blank_lines = 0
        for path in files:
            markdown = path.read_text(encoding="utf-8-sig")
            shown = skill_notes.reading_text(markdown)
            if "\n\n" in shown:
                sources_with_blank_lines += 1
            with self.subTest(path=path.name):
                self.assertFalse(
                    _has_blank_line_outside_code(skill_note_render.parse(shown)),
                    "代码块外仍出现连续空行",
                )
        self.assertGreater(sources_with_blank_lines, 0, "样例应确实包含原始空行")

    def test_note_text_uses_tokenized_paragraph_spacing(self):
        """REQ-S02-32：段距来自 ui_tokens，且不超过半行高。"""
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        widget = tk.Text(root, wrap="word")
        skill_note_render.apply(widget, "# 标题\n\n正文第一段\n\n- 条目\n\n正文第二段")
        content = widget.get("1.0", "end-1c")
        self.assertNotIn("\n\n", content)
        spacing = int(float(widget.tag_cget(skill_note_render.BODY, "spacing3")))
        token = int(getattr(ui_tokens, "NOTE_PARAGRAPH_SPACING", 0))
        self.assertEqual(spacing, token)
        self.assertGreater(spacing, 0)
        line_height = tkfont.Font(font=ui_tokens.FONTS["body"]).metrics("linespace")
        self.assertLessEqual(spacing * 2, line_height)

    def test_code_block_blank_lines_are_kept(self):
        """REQ-S02-32：代码块内空白属于内容，不能一并折叠。"""
        fragments = skill_note_render.parse("正文\n\n```text\n第一行\n\n第二行\n```\n\n结尾")
        code = "".join(text for text, tags in fragments
                       if skill_note_render.CODE_BLOCK in tags)
        body = "".join(text for text, tags in fragments
                       if skill_note_render.BODY in tags and text != "\n")
        compact_code = code.replace(skill_note_render._CODE_INDENT, "")
        self.assertIn("第一行\n\n第二行", compact_code)
        self.assertIn("正文", body)
        self.assertIn("结尾", body)


class ScriptDensityTests(unittest.TestCase):
    def test_compact_display_removes_only_blank_lines_outside_code(self):
        """REQ-S02-32：剧本展示文本折叠普通空行，保留代码块内容。"""
        import script_view_style

        source = (
            "第 1 集\r\n\r\n场景 1：旧站台\r\n\r\n\r\n"
            "阿远：我回来了。\r\n\r\n```text\r\n第一行\r\n\r\n第二行\r\n```\r\n\r\n结尾"
        )
        shown = script_view_style.compact_display(source)
        self.assertNotIn("\r", shown)
        self.assertIn("第一行\n\n第二行", shown)
        before, fenced = shown.split("```text\n", 1)
        code, after = fenced.split("\n```", 1)
        self.assertNotIn("\n\n", before)
        self.assertNotIn("\n\n", after)
        self.assertIn("\n\n", code)

    def test_unchanged_edit_save_preserves_source_bytes(self):
        """REQ-S02-32：进入编辑后未作改动，自动保存不触发，源文件逐字节保持不变。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = _make_project(td)
            source = writing / "script_raw.md"
            original = b"\xef\xbb\xbf" + (
                "第 1 集\r\n\r\n场景 1：旧站台\r\n\r\n阿远：我回来了。\r\n\r\n\r\n结尾"
            ).encode("utf-8")
            source.write_bytes(original)
            win = tk.Tk()
            win.geometry("1280x800+40+40")
            win.deiconify()
            win.update()
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            desktop = _show_script_structure(win, project)
            preview = desktop.script_structure_source_preview

            desktop.script_structure_source_preview_edit_button.invoke()
            win.update()
            self.assertEqual(str(preview.cget("state")), "normal")

            self.assertEqual(source.read_bytes(), original)

    def test_script_text_and_directory_get_the_requested_space(self):
        """REQ-S02-32：1280×800 下正文占宽至少 85%，目录按 1..6 行紧凑显示。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = _make_project(td)
            structured = writing / "结构剧本"
            structured.mkdir()
            for index in range(3):
                (structured / ("script%d.md" % index)).write_text(
                    "# 结构化剧本\n\n## 分场剧本\n\n" + "\n\n".join(
                        "正稿行%d-%d" % (index, row) for row in range(20)
                    ) + "\n",
                    encoding="utf-8",
                )
            win = tk.Tk()
            win.geometry("1280x800+40+40")
            win.deiconify()
            win.update()
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            desktop = _show_script_structure(win, project)

            for box, preview, tree in (
                (desktop.script_structure_source_box,
                 desktop.script_structure_source_preview,
                 desktop.script_structure_source_preview_files),
                (desktop.script_structure_output_box,
                 desktop.script_structure_output_preview,
                 desktop.script_structure_output_preview_files),
            ):
                with self.subTest(box=str(box)):
                    self.assertGreaterEqual(
                        preview.winfo_width() / max(1, box.winfo_width()),
                        0.85,
                    )
                    line_height = tkfont.Font(font=preview.cget("font")).metrics("linespace")
                    self.assertGreaterEqual(
                        preview.winfo_height(),
                        box.winfo_height() - line_height * 2,
                    )
                    # 文件选择已改为正文上方的横向下拉框，不再占用左侧目录列。
                    self.assertEqual(str(tree.winfo_class()), "TCombobox")
                    self.assertLess(tree.winfo_rooty(), preview.winfo_rooty())
                    self.assertEqual(len(tree["values"]), max(1, len(tree.get_children())))

    def test_many_documents_listed_in_dropdown(self):
        """文件很多时全部进入下拉框。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = _make_project(td)
            structured = writing / "结构剧本"
            structured.mkdir()
            for index in range(8):
                (structured / ("script%d.md" % index)).write_text(
                    "# 结构化剧本\n\n## 分场剧本\n\n正文%d\n" % index,
                    encoding="utf-8",
                )
            win = tk.Tk()
            win.geometry("1280x800+40+40")
            win.deiconify()
            win.update()
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            desktop = _show_script_structure(win, project)
            tree = desktop.script_structure_output_preview_files

            self.assertEqual(len(tree.get_children()), 8)
            self.assertEqual(len(tree["values"]), 8)

    def test_long_document_name_does_not_squeeze_reading_area(self):
        """REQ-S02-32：最长文件名仍把正文宽度留在内容框的 85% 以上。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = _make_project(td)
            structured = writing / "结构剧本"
            structured.mkdir()
            long_name = "超长剧本文档名称用于验证目录栏宽度不会挤压正文阅读区域" * 2 + ".md"
            (structured / long_name).write_text(
                "# 结构化剧本\n\n## 分场剧本\n\n正文\n",
                encoding="utf-8",
            )
            win = tk.Tk()
            win.geometry("1280x800+40+40")
            win.deiconify()
            win.update()
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            desktop = _show_script_structure(win, project)

            box = desktop.script_structure_output_box
            preview = desktop.script_structure_output_preview
            self.assertGreaterEqual(preview.winfo_width() / max(1, box.winfo_width()), 0.85)
            tree = desktop.script_structure_output_preview_files
            self.assertEqual(tree["values"][0], long_name)


if __name__ == "__main__":
    unittest.main()
