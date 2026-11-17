# -*- coding: utf-8 -*-
"""会话分支/节点树 UI（R3132）：DataTable 缩进树 + 切换节点 + 延续/独立提问。

运行：python tests/test_branch_tree_ui.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skip_reasons import PLATFORM_TKINTER
from ui import ui_branch_tree


class BranchTreeTests(unittest.TestCase):
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

    def test_tree_renders_children_and_emit_switch_and_ask(self):
        switched, asked = [], []
        nodes = [
            {'id': 'c1', 'parent_id': '', 'label': '初始'},
            {'id': 'c2', 'parent_id': 'c1', 'label': '分支A'},
            {'id': 'c3', 'parent_id': 'c1', 'label': '分支B'},
        ]
        frame = ui_branch_tree.build_branch_tree(
            self.win, nodes, current_id='c2',
            on_switch=switched.append, on_ask=lambda node_id, mode: asked.append((node_id, mode)))
        table = frame.winfo_children()[0]
        tree = table.tree
        self.assertEqual(len(tree.get_children('')), 3)
        self.assertEqual(tree.item('c1', 'text'), '初始')
        self.assertTrue(tree.item('c2', 'text').endswith('分支A'), '子节点缩进后的文字仍是分支名')
        self.assertNotEqual(tree.item('c2', 'text'), '分支A', '子节点应带缩进')
        self.assertEqual(tree.selection(), ('c2',))
        tree.selection_set('c3')
        buttons = {child.cget('text'): child for child in frame.winfo_children()[1].winfo_children()
                   if child.winfo_class() == 'TButton'}
        buttons['切换到此节点'].invoke()
        buttons['延续提问'].invoke()
        buttons['独立提问'].invoke()
        self.assertEqual(switched, ['c3'])
        self.assertEqual(asked, [('c3', 'continue'), ('c3', 'independent')])


if __name__ == '__main__':
    unittest.main()
