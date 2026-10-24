# -*- coding: utf-8 -*-
"""R1970 按钮一致性：最小宽度显式化、内边距改动与按下态同步。

1. 全部按钮样式显式声明最小宽度 ``BUTTON_MIN_WIDTH``（此前靠 clam 隐含的 -11）；
2. ``set_button_padding`` 改内边距后，按下态内边距同步重算，按下不回弹到旧高度；
3. 侧栏紧凑切换（fit_sidebar 所用令牌）前后，按钮常态与按下态总高一致。
"""
from __future__ import annotations

import re
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

import ui_theme
from ui_rounded import set_button_padding
from ui_tokens import (BUTTON_GAP, BUTTON_GAP_TIGHT, BUTTON_MIN_WIDTH, NAV_PADDING_X,
                       NAV_PADDING_Y, NAV_PADDING_Y_COMPACT, SPACING)

ROOT = Path(__file__).resolve().parents[1]
DIALOG_FILES = ("asset_reference_import.py", "seedream_settings.py", "reference_wall.py",
                "background_characters.py", "skill_panel_presets.py", "skill_panel_workflow.py",
                "pet_models_ui.py")

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


class ButtonRuleContractTests(unittest.TestCase):
    """R1973：页面不再各自维护按钮宽度常量；弹窗底栏「取消／关闭」紧贴主操作左侧，间距取 BUTTON_GAP。"""

    def test_page_width_constants_come_from_tokens(self):
        import desktop_page_support
        import desktop_script_pages
        from ui_tokens import BUTTON_WIDTH_EDIT, BUTTON_WIDTH_STAGE, CHAR_WIDTH
        self.assertEqual(desktop_page_support.STAGE_ACTION_WIDTH, BUTTON_WIDTH_STAGE)
        self.assertEqual(desktop_script_pages.SCRIPT_EDIT_BUTTON_WIDTH, BUTTON_WIDTH_EDIT)
        self.assertEqual(BUTTON_WIDTH_STAGE, CHAR_WIDTH["3xl"])

    def test_dialog_cancel_buttons_are_right_packed_with_the_gap_token(self):
        pattern = re.compile(r"text='(取消|关闭)'.*pack\(")
        for name in DIALOG_FILES:
            text = (ROOT / name).read_text(encoding="utf-8")
            lines = text.splitlines()
            for index, line in enumerate(lines):
                if not pattern.search(line):
                    continue
                call = " ".join(lines[index:index + 2])
                with self.subTest(file=name, line=index + 1):
                    self.assertIn("side='right'", call.replace('"', "'"), "取消／关闭必须靠右，紧挨主操作左侧")
                    self.assertIn("BUTTON_GAP", call, "取消／关闭与主操作的间距必须取 BUTTON_GAP")


if __name__ == "__main__":
    unittest.main()
