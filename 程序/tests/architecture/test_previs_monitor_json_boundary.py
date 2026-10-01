"""白模监视页的正式进度 JSON 必须经缓存入口读取。"""
import ast
import unittest
from pathlib import Path


class PrevisMonitorJsonBoundaryTests(unittest.TestCase):
    def test_progress_reader_uses_cache(self):
        source = Path(__file__).resolve().parents[2] / 'previs_monitor.py'
        text = source.read_text(encoding='utf-8')
        tree = ast.parse(text)
        method = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'progress_of')
        calls = [node for node in ast.walk(method)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertIn('from file_cache import read_json', text)
        self.assertTrue(any(node.func.id == 'read_json' for node in calls))
        self.assertFalse(any(node.func.id == 'loads' for node in calls))


if __name__ == '__main__':
    unittest.main()
