import ast
import os
import unittest
from pathlib import Path

from tests.architecture._scan import entity_file

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class WhiteModelImportBoundaryTests(unittest.TestCase):
    def test_picker_delegates_media_publication_to_service(self):
        source = entity_file('white_model').read_text(encoding='utf-8')
        tree = ast.parse(source)
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'import_media')
        text = ast.get_source_segment(source, method)
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'import_media']
        self.assertEqual(len(calls), 1)
        self.assertTrue(any(keyword.arg == 'importer' for keyword in calls[0].keywords))
        self.assertNotIn('copy2', text)
        self.assertNotIn('write_record(', text)
