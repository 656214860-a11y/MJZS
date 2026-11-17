# -*- coding: utf-8 -*-
"""红绿 Diff 视图（R3124）：行级差异 + 红删绿增 + 接受/拒绝。

运行：python tests/test_diff_view.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skip_reasons import PLATFORM_TKINTER
from ui import ui_diff


class DiffViewTests(unittest.TestCase):
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

    def test_diff_lines_marks_delete_and_insert(self):
        rows = ui_diff.diff_lines('A\nB\nC', 'A\nX\nC')
        self.assertEqual([line for op, line in rows if op == ui_diff.OP_DELETE], ['B'])
        self.assertEqual([line for op, line in rows if op == ui_diff.OP_INSERT], ['X'])
        self.assertEqual([line for op, line in rows if op == ui_diff.OP_EQUAL], ['A', 'C'])

    def test_build_diff_view_renders_red_green_and_emits_decisions(self):
        seen = []
        frame = ui_diff.build_diff_view(self.win, '旧台词', '新台词', seen.append)
        box, row = frame.winfo_children()
        content = box.get('1.0', 'end-1c')
        self.assertIn('- 旧台词', content)
        self.assertIn('+ 新台词', content)
        buttons = [child for child in row.winfo_children() if child.winfo_class() == 'TButton']
        buttons[0].invoke()
        buttons[1].invoke()
        self.assertEqual(seen, ['approve', 'reject'])


if __name__ == '__main__':
    unittest.main()
