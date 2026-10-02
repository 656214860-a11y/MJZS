import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class AssetGeneratedImportBoundaryTests(unittest.TestCase):
    def test_l2_requires_injected_byte_publisher(self):
        tree = ast.parse((ROOT / 'asset_generated_import_service.py').read_text(encoding='utf-8'))
        imported = [name.name for node in tree.body if isinstance(node, ast.ImportFrom)
                    and node.module == 'agent.core' for name in node.names]
        self.assertNotIn('save_bytes', imported)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'import_pending_generated')
        self.assertIn('gateway', {arg.arg for arg in function.args.kwonlyargs})
