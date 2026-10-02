"""全局滚动条样式必须经 token 入口统一。"""
import ast
import unittest
from pathlib import Path


PROGRAM = Path(__file__).resolve().parents[2]


class ScrollbarThemeBoundaryTests(unittest.TestCase):
    def test_both_standard_scrollbar_orientations_use_shared_tokens_and_active_state(self):
        tree = ast.parse((PROGRAM / 'ui_theme.py').read_text(encoding='utf-8'))
        source = ast.unparse(tree)
        for token in ('SCROLLBAR_THUMB', 'SCROLLBAR_THUMB_ACTIVE', 'SCROLLBAR_TROUGH',
                      'SCROLLBAR_ARROW', 'SCROLLBAR_BORDER_WIDTH'):
            self.assertIn(token, source)
        self.assertIn("'Vertical.TScrollbar'", source)
        self.assertIn("'Horizontal.TScrollbar'", source)
        self.assertIn("('active', SCROLLBAR_THUMB_ACTIVE)", source)
