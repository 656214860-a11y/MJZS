# -*- coding: utf-8 -*-
"""R1970 按钮一致性：最小宽度显式化、内边距改动与按下态同步。

1. 全部按钮样式显式声明最小宽度 ``BUTTON_MIN_WIDTH``（此前靠 clam 隐含的 -11）；
2. ``set_button_padding`` 改内边距后，按下态内边距同步重算，按下不回弹到旧高度；
3. 侧栏紧凑切换（fit_sidebar 所用令牌）前后，按钮常态与按下态总高一致。
"""
from __future__ import annotations

import tkinter as tk
import unittest
from tkinter import ttk

import ui_theme
from ui_rounded import set_button_padding
from ui_tokens import (BUTTON_GAP, BUTTON_GAP_TIGHT, BUTTON_MIN_WIDTH, NAV_PADDING_X,
                       NAV_PADDING_Y, NAV_PADDING_Y_COMPACT, SPACING)

STYLES = ("TButton", "Primary.TButton", "Tokens.Primary.TButton", "Tokens.Secondary.TButton",
          "Tokens.Danger.TButton", "Tokens.Icon.TButton", "Tokens.Text.TButton",
          "Compact.TButton", "Nav.TButton", "Sub.Nav.TButton")


class ButtonConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        ui_theme.apply(self.root)
        self.style = ttk.Style(self.root)

    def test_every_variant_declares_the_minimum_width(self):
        for name in STYLES:
            with self.subTest(style=name):
                self.assertEqual(int(self.style.lookup(name, "width")), -BUTTON_MIN_WIDTH)

    def test_gap_tokens_follow_the_4px_scale(self):
        self.assertEqual(BUTTON_GAP, SPACING["sm"])
        self.assertEqual(BUTTON_GAP_TIGHT, SPACING["xs"])

    def test_set_button_padding_keeps_pressed_state_in_sync(self):
        for pad_y in (NAV_PADDING_Y, NAV_PADDING_Y_COMPACT):
            set_button_padding(self.style, "Nav.TButton", (NAV_PADDING_X, pad_y))
            with self.subTest(pad_y=pad_y):
                normal = [int(v) for v in str(self.style.lookup("Nav.TButton", "padding")).split()]
                pressed = [int(v) for v in str(self.style.lookup("Nav.TButton", "padding", ["pressed"])).split()]
                self.assertEqual(2 * normal[1], pressed[1] + pressed[3],
                                 "按下态上下内边距之和必须等于常态，按下不得改变总高")
                self.assertEqual(pressed[1], pad_y + 1, "按下态必须以新内边距为基准")


if __name__ == "__main__":
    unittest.main()
