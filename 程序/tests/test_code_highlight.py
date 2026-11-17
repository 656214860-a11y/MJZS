# -*- coding: utf-8 -*-
"""代码/提示词高亮块（R3124）：JSON 词法高亮 + 收起/展开 + 复制 + 应用。

运行：python tests/test_code_highlight.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skip_reasons import PLATFORM_TKINTER
from ui import ui_code_block


class CodeHighlightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)

    def test_highlight_tokens_marks_json_kinds(self):
        rows = ui_code_block.highlight_tokens('{"a": 1, "b": true}')
        kinds = [kind for _, kind in rows]
        self.assertIn('string', kinds)
        self.assertIn('number', kinds)
        self.assertIn('keyword', kinds)

    def test_build_code_block_copy_apply_and_toggle(self):
        copied, applied = [], []
        frame = ui_code_block.build_code_block(self.win, '{"a": 1}',
                                               on_copy=copied.append, on_apply=applied.append)
        box, row = frame.winfo_children()
        self.assertIn('"a"', box.get('1.0', 'end-1c'))
        buttons = {child.cget('text'): child for child in row.winfo_children()
                   if child.winfo_class() == 'TButton'}
        self.assertEqual(set(buttons), {'收起', '复制', '应用此提示词'})
        buttons['收起'].invoke()
        self.assertEqual(int(box.cget('height')), 1)
        self.assertEqual(buttons['收起'].cget('text'), '展开')
        buttons['复制'].invoke()
        buttons['应用此提示词'].invoke()
        self.assertEqual(copied, ['{"a": 1}'])
        self.assertEqual(applied, ['{"a": 1}'])


if __name__ == '__main__':
    unittest.main()
