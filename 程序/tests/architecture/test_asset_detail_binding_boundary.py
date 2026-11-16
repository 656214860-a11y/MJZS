import ast
import os
import unittest
from pathlib import Path

from tests.architecture._scan import entity_file

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AssetDetailBindingBoundaryTests(unittest.TestCase):
    def test_detail_ui_delegates_all_image_publication_to_service(self):
        path = os.path.join(ROOT, 'asset_detail.py')
        source = Path(path).read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for name, service in (('bind_view', 'bind_asset_canonical_view'), ('_bind_variant_image', 'bind_asset_variant_thumbnail')):
            method_source = ast.get_source_segment(source, methods[name])
            calls = [node for node in ast.walk(methods[name]) if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == service]
            self.assertEqual(len(calls), 1)
            self.assertNotIn('copy2', method_source)
            self.assertNotIn('_fields(', method_source)

    def test_service_requires_l3_gateway_and_has_no_direct_byte_publisher(self):
        source = entity_file('asset_detail_service').read_text(encoding='utf-8')
        tree = ast.parse(source)
        imports = [name.name for node in tree.body if isinstance(node, ast.ImportFrom)
                   and node.module == 'agent.core' for name in node.names]
        self.assertNotIn('save_bytes', imports)
        publish = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                       and node.name == '_publish')
        self.assertIn('gateway', {arg.arg for arg in publish.args.kwonlyargs})
