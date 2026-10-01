"""视频生成入口的正式项目 JSON 必须经统一缓存入口读取。"""
import ast
import unittest
from pathlib import Path


class VideoNavigationJsonBoundaryTests(unittest.TestCase):
    def test_display_reader_wraps_file_cache(self):
        source = Path(__file__).resolve().parents[2] / 'video_navigation.py'
        text = source.read_text(encoding='utf-8')
        tree = ast.parse(text)
        reader = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'read_json')
        calls = [node for node in ast.walk(reader)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertIn('from file_cache import read_json as read_cached_json', text)
        self.assertTrue(any(node.func.id == 'read_cached_json' for node in calls))
        self.assertFalse(any(node.func.id == 'loads' for node in calls))


if __name__ == '__main__':
    unittest.main()
