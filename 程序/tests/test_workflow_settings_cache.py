"""工作流调用设置的正式 JSON 必须复用缓存。"""
import tempfile
import unittest

import workflow_settings


class WorkflowSettingsCacheTests(unittest.TestCase):
    def test_atomic_model_sync_invalidates_cached_settings_read(self):
        with tempfile.TemporaryDirectory() as project:
            workflow_settings.sync_qwen_model(project, 'qwen-first')
            self.assertEqual(workflow_settings.load(project)['profiles']['qwen']['model'], 'qwen-first')
            workflow_settings.sync_qwen_model(project, 'qwen-second')
            self.assertEqual(workflow_settings.load(project)['profiles']['qwen']['model'], 'qwen-second')


if __name__ == '__main__':
    unittest.main()
