# -*- coding: utf-8 -*-
"""侧栏导航行按下态不裁字：改按钮内边距必须连按下映射一起改。

fit_sidebar 按窗口高度把导航行内边距压到 (10,4)（行高 29px，正好一个字体行高）。
ttk 的 padding 映射是绝对值：只有在样式创建时登记过按下映射、之后又被别处
configure(padding=...) 改小的样式，按下瞬间会按旧基准 (12,9,12,7) 排版——
行高不变，文字区从 19px 掉到 11px，被点的那一行文字上下各被裁掉 4px（用户看到的「遮挡」）。
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
import unittest
from tkinter import ttk

import ui_theme
import ui_widgets
from ui_tokens import FONTS


class NavPressPaddingTests(unittest.TestCase):
    """真 Tk 量控件几何：按下态的文字区不得小于一个字体行高。"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("240x400+6000+6000")   # 离屏摆放，不弹到用户桌面
        self.addCleanup(self.root.destroy)
        ui_theme.apply(self.root)
        self.style = ttk.Style(self.root)
        self.linespace = tkfont.Font(font=FONTS["body"]).metrics("linespace")

    def _row(self, name="Nav.TButton"):
        row = ui_widgets.SecondaryButton(self.root, text="03  初步分镜", style=name)
        row.pack(anchor="w", fill="x")
        self.addCleanup(row.destroy)
        self.root.update()
        return row

    def _label_band(self, row):
        """identify 逐像素回推 label 元素占的高度：ttk 裁字时这里会塌下去。"""
        band = [y for y in range(row.winfo_height()) if row.identify(30, y) == "label"]
        return (max(band) - min(band) + 1) if band else 0

    def test_pressed_row_keeps_a_full_text_line_after_padding_shrinks(self):
        row = self._row()
        ui_widgets.set_button_padding(self.style, "Nav.TButton", (10, 4))
        self.root.update()
        normal_height = row.winfo_height()
        self.assertGreaterEqual(self._label_band(row), self.linespace,
                                "常态导航行已经放不下一个字体行高")
        row.state(["pressed"])
        self.root.update()
        self.assertEqual(row.winfo_height(), normal_height, "按下不应改变行高")
        self.assertGreaterEqual(
            self._label_band(row), self.linespace,
            "按下态文字区 %dpx < 行高 %dpx：内边距映射还停在样式创建时的基准上，文字被裁"
            % (self._label_band(row), self.linespace))

    def test_padding_helper_keeps_colour_maps(self):
        """只改按下映射，不能顺手清掉 fill／foreground 的状态映射。"""
        self._row()
        ui_widgets.set_button_padding(self.style, "Nav.TButton", (10, 4))
        self.assertTrue(self.style.map("Nav.TButton", "fill"), "按下／悬停底色映射被清掉了")
        self.assertTrue(self.style.map("Nav.TButton", "foreground"), "文字色映射被清掉了")
        self.assertEqual(str(self.style.lookup("Nav.TButton", "padding")),
                         "10 4", "常态内边距没落到 (10,4)")

    def test_sub_and_selected_nav_rows_keep_a_full_text_line(self):
        for name in ("Sub.Nav.TButton", "Selected.Nav.TButton",
                     "Selected.Sub.Nav.TButton"):
            with self.subTest(style=name):
                row = self._row(name)
                horizontal = 26 if "Sub" in name else 10
                ui_widgets.set_button_padding(self.style, name, (horizontal, 4))
                self.root.update()
                row.state(["pressed"])
                self.root.update()
                self.assertGreaterEqual(self._label_band(row), self.linespace,
                                        "%s 按下态文字被裁" % name)


if __name__ == "__main__":
    unittest.main()
