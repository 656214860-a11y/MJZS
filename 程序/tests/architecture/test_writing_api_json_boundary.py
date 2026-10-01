"""剧本 API 的已确认简报必须经正式缓存入口读取。"""
import ast
import unittest
from pathlib import Path


class WritingApiJsonBoundaryTests(unittest.TestCase):
    def test_complete_brief_uses_cache_for_formal_brief_json(self):
        source = Path(__file__).resolve().parents[2] / 'writing_api.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                   and node.module == 'file_cache']
        self.assertTrue(any(any(alias.name == 'read_json' for alias in node.names) for node in imports))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == '_complete_brief')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertTrue(any(node.func.id == 'read_json' for node in calls))
        self.assertFalse(any(node.func.id == 'loads' for node in calls))


if __name__ == '__main__':
    unittest.main()
