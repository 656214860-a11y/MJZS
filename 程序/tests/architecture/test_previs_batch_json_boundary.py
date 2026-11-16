"""白模批处理消费正式分镜 JSON 时必须复用缓存入口。"""
import ast
import unittest

from tests.architecture._scan import entity_file


class PrevisBatchJsonBoundaryTests(unittest.TestCase):
    def test_prepare_batch_uses_cache_for_episode_json(self):
        source = entity_file('previs_batch_service')
        tree = ast.parse(source.read_text(encoding='utf-8'))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                   and node.module == 'file_cache']
        self.assertTrue(any(any(alias.name == 'read_json' for alias in node.names) for node in imports))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == 'prepare_batch')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertTrue(any(node.func.id == 'read_json' for node in calls))
        self.assertFalse(any(node.func.id == 'loads' for node in calls))


if __name__ == '__main__':
    unittest.main()
