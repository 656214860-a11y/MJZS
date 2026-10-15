from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import unittest
from tests.architecture._scan import ROOT


class KeyframeDeleteBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_keyframe_delete_persistence(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'delete_keyframe')
        self.assertEqual(1, sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                                and n.func.id == 'delete_stage_keyframe' for n in ast.walk(method)))
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id == 'save' for n in ast.walk(method)))
