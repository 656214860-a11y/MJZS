from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import unittest

from tests.architecture._scan import ROOT


class KeyframeRestoreBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_keyframe_restore_persistence(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'restore_keyframe')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertEqual(1, sum(isinstance(node.func, ast.Name)
                                and node.func.id == 'restore_stage_keyframe' for node in calls))
        prohibited = {'save', 'save_bytes', 'write_text', 'write_bytes', 'copy2', 'remove_temporary_file'}
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id in prohibited
                             for node in calls))
