import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DeliveryImportBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_final_import_to_l3_orchestrator(self):
        tree = ast.parse(open(os.path.join(ROOT, 'desktop.py'), encoding='utf-8').read())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'final_import')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'import_delivery_master']
        self.assertEqual(len(calls), 1)
        service = open(os.path.join(ROOT, 'stage_execution_service.py'), encoding='utf-8').read()
        self.assertIn('publish=publish_stage_bytes', service,
                      '生产交付导入必须由 L3 注入统一二进制发布器')
        self.assertNotIn('copy2', ast.get_source_segment(open(os.path.join(ROOT, 'desktop.py'), encoding='utf-8').read(), method))
