"""白模预演记录的正式 JSON 读取必须复用缓存入口。"""
import ast
import unittest
from pathlib import Path

from tests.architecture._scan import entity_file


class WhiteModelServiceJsonBoundaryTests(unittest.TestCase):
    def test_read_record_uses_cache_for_formal_record(self):
        source = entity_file('white_model_service')
        tree = ast.parse(source.read_text(encoding='utf-8'))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                   and node.module in {'file_cache', 'infra.file_cache'}]
        self.assertTrue(any(any(alias.name == 'read_json' for alias in node.names) for node in imports))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == 'read_record')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertTrue(any(node.func.id == 'read_json' for node in calls))
        self.assertFalse(any(node.func.id == 'loads' for node in calls))

    def test_record_publication_is_injected_not_imported(self):
        source = entity_file('white_model_service')
        tree = ast.parse(source.read_text(encoding='utf-8'))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertFalse(any(node.module == 'agent.core' for node in imports))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == 'write_record')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertTrue(any(isinstance(node.func, ast.Name) and node.func.id == 'publish'
                            for node in calls))


if __name__ == '__main__':
    unittest.main()
