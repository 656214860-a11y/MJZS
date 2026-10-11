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
        self.assertIn("publish=media_import_publisher(project, 'video')", service,
                      '生产交付导入必须由 L3 注入统一媒体校验及流式发布器')
        self.assertIn('return copy_file_new(target, source, lambda temporary: validate_import(temporary, config, kind))', service)
        self.assertNotIn('copy2', ast.get_source_segment(open(os.path.join(ROOT, 'desktop.py'), encoding='utf-8').read(), method))

    def test_l2_requires_l3_publisher_without_copy_fallback(self):
        service = open(os.path.join(ROOT, 'delivery_import_service.py'), encoding='utf-8').read()
        self.assertIn("if not callable(publish):", service)
        self.assertNotIn('shutil.copy2', service)
        self.assertNotIn('read_bytes(', service, '成片导入不能整文件读入内存')
