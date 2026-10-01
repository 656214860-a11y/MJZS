import ast
import os
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AssetDetailBindingBoundaryTests(unittest.TestCase):
    def test_detail_ui_delegates_all_image_publication_to_service(self):
        path = os.path.join(ROOT, 'asset_detail.py')
        source = Path(path).read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for name, service in (('bind_view', 'bind_canonical_view'), ('_bind_variant_image', 'bind_variant_thumbnail')):
            method_source = ast.get_source_segment(source, methods[name])
            calls = [node for node in ast.walk(methods[name]) if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == service]
            self.assertEqual(len(calls), 1)
            self.assertNotIn('copy2', method_source)
            self.assertNotIn('_fields(', method_source)
