"""首帧批次消费正式分镜 JSON 时必须走缓存入口。"""
import ast
import unittest
from pathlib import Path

from tests.architecture._scan import entity_file


class KeyframeBatchJsonBoundaryTests(unittest.TestCase):
    def test_candidates_uses_cache_for_episode_json(self):
        source = entity_file('keyframe_batch')
        tree = ast.parse(source.read_text(encoding='utf-8'))
        self.assertIn('from file_cache import read_json', source.read_text(encoding='utf-8'))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == 'candidates')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertTrue(any(node.func.id == 'read_json' for node in calls))
        self.assertFalse(any(node.func.id == 'loads' for node in calls))


if __name__ == '__main__':
    unittest.main()
