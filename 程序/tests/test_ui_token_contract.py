# -*- coding: utf-8 -*-
"""R1689 设计契约：文字对比度、橙色退场、控件尺寸，以及 design_tokens.md 与 ui_tokens.py 一致。"""
import re
import unittest
from pathlib import Path

import ui_tokens
from ui_tokens import COLORS, CONTROL_HEIGHT, CONTROL_HIT_MIN, FONTS

ROOT = Path(__file__).resolve().parents[1]
MIN_CONTRAST = 4.5


def _luminance(value):
    channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground, background):
    high, low = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class UiTokenContractTests(unittest.TestCase):
    def test_readable_text_tokens_meet_contrast_on_card_and_page_background(self):
        # REQ-UI-THEME-1：两套调色板都要过——页面文字色用 primary_text（夜间提亮档），
        # 不再拿实心填充色 primary 当文字色。
        for theme, palette in ui_tokens.THEMES.items():
            for text in ('text_primary', 'text_secondary', 'text_muted', 'warning_text',
                         'success_text', 'danger_text', 'primary_text'):
                for background in ('background_card', 'background_primary'):
                    with self.subTest(theme=theme, text=text, background=background):
                        self.assertGreaterEqual(contrast(palette[text], palette[background]), MIN_CONTRAST)

    def test_filled_buttons_keep_white_text_readable(self):
        # 实心按钮字色是 on_accent（与表面色拆开，REQ-UI-THEME-1），两套调色板都验。
        for theme, palette in ui_tokens.THEMES.items():
            for fill in ('primary', 'primary_hover', 'primary_pressed', 'danger'):
                with self.subTest(theme=theme, fill=fill):
                    self.assertGreaterEqual(contrast(palette['on_accent'], palette[fill]), MIN_CONTRAST)

    def test_disabled_text_is_a_separate_token_from_muted_text(self):
        self.assertNotEqual(COLORS['disabled_text'], COLORS['text_muted'])

    def test_orange_accent_tokens_are_retired(self):
        for name in ('emphasis', 'emphasis_pressed', 'warning_hover', 'warning_pressed'):
            self.assertNotIn(name, COLORS)

    def test_compact_control_size_contract(self):
        self.assertEqual((CONTROL_HEIGHT, CONTROL_HIT_MIN), (36, 36))
        self.assertEqual(FONTS['body'][1], 10)

    def test_design_tokens_doc_lists_every_color_and_font_in_code(self):
        doc = (ROOT / 'design_tokens.md').read_text(encoding='utf-8')
        documented = {value.upper() for value in re.findall(r'`(#[0-9A-Fa-f]{6})`', doc)}
        missing = sorted(name for name, value in COLORS.items() if value.upper() not in documented)
        self.assertEqual(missing, [], '以下颜色令牌在 design_tokens.md 中没有登记：%s' % missing)
        for name in ('heading_1', 'title', 'body', 'caption', 'hint', 'numeric'):
            self.assertIn('`%s`' % name, doc)
        self.assertIn('CONTROL_HEIGHT', doc)
        self.assertTrue(hasattr(ui_tokens, 'CONTROL_HEIGHT'))


if __name__ == '__main__':
    unittest.main()
