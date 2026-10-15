"""Legacy-adoption log persistence belongs to its no-Tk service."""
from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import unittest

from tests.architecture._scan import ROOT


class LegacyAdoptionBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_legacy_adoption_log_persistence(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in desktop.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'record_legacy_adoption')
        calls = [node.func.id for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('record_stage_legacy_adoption', calls)
        direct = [node.lineno for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr in {'mkdir', 'save'}]
        self.assertEqual([], direct, '旧目录归位日志不得由桌面页直接发布: ' + str(direct))
        service = (ROOT / 'legacy_adoption_service.py').read_text(encoding='utf-8')
        stage = (ROOT / 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertNotIn('from agent.core import save', service)
        self.assertIn('def legacy_adoption_gateway()', stage)
        self.assertIn('def record_stage_legacy_adoption(', stage)
