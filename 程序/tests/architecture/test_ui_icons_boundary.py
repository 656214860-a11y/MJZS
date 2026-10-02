"""首迁页面不得退回手写 PhotoImage。"""
import ast
import unittest
from pathlib import Path


PROGRAM = Path(__file__).resolve().parents[2]


class UiIconsBoundaryTests(unittest.TestCase):
    def test_video_back_uses_shared_icon_loader(self):
        tree = ast.parse((PROGRAM / 'video_navigation.py').read_text(encoding='utf-8'))
        show_back = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'show_back')
        source = ast.unparse(show_back)
        self.assertIn('IconLoader.return_arrow', source)
        self.assertNotIn('PhotoImage(', source)
