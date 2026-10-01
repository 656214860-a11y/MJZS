import ast
import unittest

from tests.architecture._scan import ROOT


class KeyframeRestoreBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_keyframe_restore_persistence(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'restore_keyframe')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertEqual(1, sum(isinstance(node.func, ast.Name)
                                and node.func.id == 'restore_stage_keyframe' for node in calls))
        prohibited = {'save', 'save_bytes', 'write_text', 'write_bytes', 'copy2', 'remove_temporary_file'}
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id in prohibited
                             for node in calls))
