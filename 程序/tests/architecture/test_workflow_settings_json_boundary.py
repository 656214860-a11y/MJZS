"""工作流调用设置的正式 JSON 必须走缓存读与原子写。"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class WorkflowSettingsJsonBoundaryTests(unittest.TestCase):
    def test_workflow_settings_use_cache_for_read_and_core_for_write(self):
        path = os.path.join(ROOT, 'workflow_settings.py')
        with open(path, encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn('from file_cache import read_json', source)
        self.assertIn('loaded=read_json(target)', source)
        self.assertIn('data=read_json(path)', source)
        self.assertIn('all_settings=read_json(path)', source)
        self.assertIn('from agent.core import save', source)
        self.assertIn('save(target,data)', source)
        self.assertIn('save(path,all_settings)', source)
        self.assertNotIn('json.loads(', source)


if __name__ == '__main__':
    unittest.main()
