# -*- coding: utf-8 -*-
"""REQ-S02-37：02 剧本结构页只留一个编辑器（原 L4-U7a 双框布局用例按新契约改写）。

T1 量唯一编辑器文本框在 1280×800 与 880×600 下落在页面可视区内，且页面上不再出现
已删除的「采用选中剧本」「手动制作结构剧本」两颗主操作按钮；
T2 断言「原剧本／结构剧本」分区字样与「大纲」「编辑」按钮全部不存在；
T3 断言页面上不再有文件下拉框（文档选择改由右侧文件面板，REQ-S02-38）；
T4 用空态文字的实际渲染位置确认它显示在唯一编辑器里。
"""
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

import infra.pet_state as pet_state  # noqa: E402
import desktop as desktop_module  # noqa: E402
import desktop_script_pages as script_pages  # noqa: E402,F401  （--affected desktop_script_pages 的消费者）
import ui_tokens  # noqa: E402

NATURAL = "第 1 集\n\n场景 1：旧站台\n\n阿远：我回来了。\n"
REMOVED_BUTTON_TEXTS = ("采用选中剧本", "手动制作结构剧本", "大纲", "编辑", "退出", "删除")
REMOVED_SECTION_TEXTS = ("原剧本", "结构剧本")


def _settle(widget, iterations=10):
    for _ in range(iterations):
        widget.update_idletasks()
        widget.update()
        time.sleep(0.03)


def _descendants(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _descendants(child)


def _buttons(widget):
    return [item for item in _descendants(widget) if isinstance(item, ttk.Button)]


def _make_project(td, structured=False):
    project = Path(td) / "project"
    writing = project / "writing"
    writing.mkdir(parents=True)
    (writing / "script_raw.md").write_text(NATURAL, encoding="utf-8")
    if structured:
        target = writing / "结构剧本"
        target.mkdir()
        (target / "script0.md").write_text(
            "# 结构化剧本\n\n## 分场剧本\n\n正文\n", encoding="utf-8")
    return project


class ScriptPageLayoutTests(unittest.TestCase):
    """真 Tk 量几何；窗口先让 Desktop 完成一次定位，再改成验收尺寸。"""

    def _open(self, project, size):
        win = tk.Tk()
        win.deiconify()
        win.update()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        try:
            desktop = desktop_module.Desktop(win, root=PROGRAM)
        finally:
            desktop_module.Desktop.choose_project = original
        win.update()  # 让 after_idle 的窗口定位先跑完，否则它会把验收尺寸改回默认值
        win.geometry(size)
        win.update()
        desktop.root = project
        desktop.show(pet_state.PAGE_OF["script_structure"])
        _settle(win)
        return win, desktop

    def _assert_editor_visible(self, desktop, label):
        preview = desktop.script_structure_editor_preview
        canvas = desktop.canvas
        top = canvas.winfo_rooty()
        bottom = top + canvas.winfo_height()
        self.assertTrue(preview.winfo_ismapped(), "%s：唯一编辑器应已映射" % label)
        self.assertGreaterEqual(
            preview.winfo_rooty(), top,
            "%s：编辑器不得被可视区上沿裁掉" % label)
        self.assertLessEqual(
            preview.winfo_rooty() + preview.winfo_height(), bottom,
            "%s：编辑器必须落在页面可视区内（底沿 %d）" % (label, bottom))
        texts = [item for item in _descendants(desktop.content) if isinstance(item, tk.Text)]
        self.assertEqual(texts, [preview], "%s：页面应只有一个文本编辑器" % label)
        buttons = [str(item.cget("text")) for item in _buttons(desktop.content)]
        for text in REMOVED_BUTTON_TEXTS:
            self.assertNotIn(text, buttons, "%s：按钮「%s」应已删除" % (label, text))

    def test_t1_single_editor_visible_at_both_sizes(self):
        """REQ-S02-37：两种窗口尺寸下唯一编辑器可见，且无已删除的主操作按钮。"""
        with tempfile.TemporaryDirectory() as td:
            win, desktop = self._open(_make_project(td), "1280x800+20+20")
            self._assert_editor_visible(desktop, "1280x800")
            win.geometry("1024x600+20+20")
            _settle(win)
            self._assert_editor_visible(desktop, "1024x600")

    def test_t2_no_section_titles_or_edit_buttons(self):
        """REQ-S02-37：「原剧本／结构剧本」字样与「大纲」「编辑」分区按钮全部删除。"""
        with tempfile.TemporaryDirectory() as td:
            win, desktop = self._open(_make_project(td), "1280x800+20+20")
            labels = [str(item.cget("text")) for item in _descendants(desktop.content)
                      if isinstance(item, ttk.Label)]
            for text in REMOVED_SECTION_TEXTS:
                self.assertNotIn(text, labels, "分区字样「%s」应已删除" % text)
            texts = [str(item.cget("text")) for item in _buttons(desktop.content)]
            self.assertNotIn("大纲", texts)
            self.assertNotIn("编辑", texts)

    def test_t3_no_document_pickers(self):
        """REQ-S02-37：两行文件下拉框删除；文档改由右侧文件面板点选。"""
        with tempfile.TemporaryDirectory() as td:
            win, desktop = self._open(_make_project(td), "1280x800+20+20")
            pickers = [item for item in _descendants(desktop.content)
                       if isinstance(item, ttk.Combobox)]
            self.assertEqual(pickers, [], "页面内容区不得再有文件下拉框")

    def test_t4_empty_state_text_inside_editor(self):
        """REQ-S02-38：空项目时编辑器显示空态说明，且文字实际渲染在文本框里。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            project.mkdir()
            win, desktop = self._open(project, "1280x800+20+20")
            preview = desktop.script_structure_editor_preview
            empty_text = preview.get("1.0", "end")
            self.assertIn("尚未找到剧本准备阶段的剧本", empty_text,
                          "空状态应解释缺哪一步的产物")
            index = preview.search("尚未找到", "1.0")
            self.assertTrue(index, "空状态文字应能定位")
            self.assertIsNotNone(preview.bbox(index),
                                 "空状态文字应实际显示在文本框里")
            box = desktop.script_structure_editor_preview_content_box
            self.assertFalse(box.close_button.winfo_ismapped(), "无当前文件时关闭×应隐藏")

    def test_t5_outline_gutter_and_close_button_stay_on_left_or_top_right(self):
        """大纲打开后位于行号左侧，行号贴正文左缘；关闭×浮在编辑器内部右上角并可聚焦。"""
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(td)
            win, desktop = self._open(project, "1280x800+20+20")
            box = desktop.script_structure_editor_preview_content_box
            preview = desktop.script_structure_editor_preview
            box.select_document(project / "writing" / "script_raw.md")
            _settle(win)
            box.aids.toggle_outline()
            _settle(win)
            self.assertEqual(box.outline.winfo_manager(), "grid")
            self.assertLess(box.outline.winfo_rootx(), box.gutter.winfo_rootx(),
                            "场次大纲应移到行号左侧")
            self.assertLess(box.gutter.winfo_rootx(), preview.winfo_rootx(),
                            "行号槽应留在正文左侧")
            button = box.close_button
            area = button.master
            self.assertTrue(button.winfo_ismapped(), "有当前文件时关闭×应可见")
            self.assertEqual(str(button.cget("text")), "×")
            self.assertNotEqual(str(button.cget("takefocus")), "0", "关闭×须可键盘聚焦")
            self.assertTrue(button.bind("<Return>"), "关闭×须有回车激活绑定")
            self.assertGreater(button.winfo_rootx(), area.winfo_rootx() + area.winfo_width() // 2,
                               "关闭×应在编辑器右半区")
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                 area.winfo_rootx() + area.winfo_width(),
                                 "关闭×不得超出编辑器右缘")
            self.assertLessEqual(button.winfo_rooty() - area.winfo_rooty(), ui_tokens.SPACING["lg"],
                                 "关闭×应贴在编辑器内部上沿")
            self.assertTrue((project / "writing" / "script_raw.md").is_file())
            button.invoke()
            _settle(win)
            self.assertIsNone(box.active["path"])
            self.assertFalse(button.winfo_ismapped())
            self.assertTrue((project / "writing" / "script_raw.md").is_file(), "关闭视图不得删除项目文件")
            box.select_document(project / "writing" / "script_raw.md")
            _settle(win)
            self.assertEqual(box.active["path"], (project / "writing" / "script_raw.md").resolve())
            self.assertTrue(button.winfo_ismapped(), "重新打开文件后关闭×应恢复可见")


if __name__ == "__main__":
    unittest.main()
