# -*- coding: utf-8 -*-
"""L4-U7a：02 剧本结构页的主操作可见、同名按钮分区与空状态方位。

T1 量两颗主操作按钮在 1280×800 与 880×600 下是否落在页面可视区内；
T2 量两个带标题的分区（原剧本／结构剧本）各自包住一组「大纲」「编辑」按钮；
T3 量两行文档下拉框的右边缘是否在同一列；
T4 用按钮与空状态文字的实际 y 判断「上方／下方」方位词是否相符。
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

NATURAL = "第 1 集\n\n场景 1：旧站台\n\n阿远：我回来了。\n"
PRIMARY_TEXTS = ("采用选中剧本", "手动制作结构剧本")
SECTION_TEXTS = ("原剧本", "结构剧本")


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


def _button_by_text(widget, text):
    matches = [item for item in _buttons(widget) if str(item.cget("text")) == text]
    return matches


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

    def _assert_primary_buttons_visible(self, desktop, label):
        canvas = desktop.canvas
        top = canvas.winfo_rooty()
        bottom = top + canvas.winfo_height()
        for text in PRIMARY_TEXTS:
            matches = _button_by_text(desktop.content, text)
            self.assertEqual(len(matches), 1, "%s：应有且只有一颗「%s」" % (label, text))
            button = matches[0]
            self.assertTrue(button.winfo_ismapped(), "%s：「%s」应已映射" % (label, text))
            self.assertGreaterEqual(
                button.winfo_rooty(), top,
                "%s：「%s」不得被可视区上沿裁掉" % (label, text))
            self.assertLessEqual(
                button.winfo_rooty() + button.winfo_height(), bottom,
                "%s：「%s」必须落在页面可视区内（底沿 %d）" % (label, text, bottom))

    def test_t1_primary_buttons_visible_at_both_sizes(self):
        with tempfile.TemporaryDirectory() as td:
            win, desktop = self._open(_make_project(td), "1280x800+20+20")
            self._assert_primary_buttons_visible(desktop, "1280x800")
            win.geometry("880x600+20+20")
            _settle(win)
            self._assert_primary_buttons_visible(desktop, "880x600")

    def test_t2_sections_are_titled_and_keep_both_button_groups(self):
        with tempfile.TemporaryDirectory() as td:
            win, desktop = self._open(_make_project(td), "1280x800+20+20")
            labels = [item for item in _descendants(desktop.content)
                      if isinstance(item, ttk.Label) and str(item.cget("text")) in SECTION_TEXTS]
            self.assertEqual(
                sorted(str(item.cget("text")) for item in labels), sorted(SECTION_TEXTS),
                "应各有一个「原剧本」「结构剧本」分区标题")
            for label in labels:
                section = label.master
                texts = [str(item.cget("text")) for item in _buttons(section)]
                title = str(label.cget("text"))
                self.assertIn("大纲", texts, "「%s」分区里应有「大纲」" % title)
                self.assertIn("编辑", texts, "「%s」分区里应有「编辑」" % title)
            self.assertEqual(len(_button_by_text(desktop.content, "大纲")), 2,
                             "上下两组「大纲」都要保留")
            self.assertEqual(len(_button_by_text(desktop.content, "编辑")), 2,
                             "上下两组「编辑」都要保留")

    def test_t3_document_pickers_share_right_edge(self):
        with tempfile.TemporaryDirectory() as td:
            win, desktop = self._open(_make_project(td), "1280x800+20+20")
            pickers = (desktop.script_structure_source_preview_files,
                       desktop.script_structure_output_preview_files)
            rights = [item.winfo_rootx() + item.winfo_width() for item in pickers]
            self.assertEqual(rights[0], rights[1],
                             "两行下拉框的右边缘应在同一列（实测 %r）" % (rights,))

    def test_t4_empty_state_direction_matches_button_position(self):
        with tempfile.TemporaryDirectory() as td:
            win, desktop = self._open(_make_project(td), "1280x800+20+20")
            preview = desktop.script_structure_output_preview
            empty_text = preview.get("1.0", "end")
            if "上方" in empty_text:
                direction = "上方"
            elif "下方" in empty_text:
                direction = "下方"
            else:
                self.fail("空状态文字缺少方位词：%r" % empty_text)
            index = preview.search("手动制作结构剧本", "1.0")
            self.assertTrue(index, "空状态文字应指向「手动制作结构剧本」")
            box = preview.bbox(index)
            self.assertIsNotNone(box, "空状态文字应实际显示在文本框里")
            text_y = preview.winfo_rooty() + box[1]
            button = _button_by_text(desktop.content, "手动制作结构剧本")[0]
            button_y = button.winfo_rooty()
            if direction == "上方":
                self.assertLess(button_y, text_y,
                                "文字写「上方」，按钮应位于文字上方（按钮 y=%d，文字 y=%d）"
                                % (button_y, text_y))
            else:
                self.assertGreater(button_y, text_y,
                                   "文字写「下方」，按钮应位于文字下方（按钮 y=%d，文字 y=%d）"
                                   % (button_y, text_y))


if __name__ == "__main__":
    unittest.main()
