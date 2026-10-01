"""Legacy-adoption log persistence belongs to its no-Tk service."""
import ast
import unittest

from tests.architecture._scan import ROOT


class LegacyAdoptionBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_legacy_adoption_log_persistence(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        method = next(node for node in desktop.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'record_legacy_adoption')
        calls = [node.func.id for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('record_legacy_adoption', calls)
        direct = [node.lineno for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr in {'mkdir', 'save'}]
        self.assertEqual([], direct, '旧目录归位日志不得由桌面页直接发布: ' + str(direct))
