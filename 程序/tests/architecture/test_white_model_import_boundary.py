import ast
import os
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class WhiteModelImportBoundaryTests(unittest.TestCase):
    def test_picker_delegates_media_publication_to_service(self):
        source = Path(ROOT, 'white_model.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'import_media')
        text = ast.get_source_segment(source, method)
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and getattr(node.func, 'attr', '') == 'import_previs_media']
        self.assertEqual(len(calls), 1)
        self.assertNotIn('copy2', text)
        self.assertNotIn('write_record(', text)
