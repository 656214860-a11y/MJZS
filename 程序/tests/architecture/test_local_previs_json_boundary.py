"""白模页面读取正式分镜时必须复用缓存入口。"""
import ast
import unittest

from tests.architecture._scan import entity_file


class LocalPrevisJsonBoundaryTests(unittest.TestCase):
    def test_show_uses_cache_for_current_episode(self):
        source = entity_file('local_previs')
        tree = ast.parse(source.read_text(encoding='utf-8'))
        self.assertIn('from infra.file_cache import read_json', source.read_text(encoding='utf-8'))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
                      and node.name == '_LocalPrevisWindow')  # R1836：show 改写成类
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertTrue(any(node.func.id == 'read_json' for node in calls))
        self.assertFalse(any(node.func.id == 'loads' for node in calls))


if __name__ == '__main__':
    unittest.main()
