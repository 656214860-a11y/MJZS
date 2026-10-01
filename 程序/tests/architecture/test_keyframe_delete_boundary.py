import ast
import unittest
from tests.architecture._scan import ROOT


class KeyframeDeleteBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_keyframe_delete_persistence(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'delete_keyframe')
        self.assertEqual(1, sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                                and n.func.id == 'delete_stage_keyframe' for n in ast.walk(method)))
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id == 'save' for n in ast.walk(method)))
