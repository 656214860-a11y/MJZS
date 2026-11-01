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

    # R2178 J1：调用设置窗口的「保存」改调 save_flow，无 Tk 也能直接验证这条写入链。
    def test_save_flow_writes_the_flow_then_syncs_shared_qwen_model(self):
        with tempfile.TemporaryDirectory() as project:
            draft = workflow_settings.defaults('storyboard')
            draft['profiles']['qwen']['model'] = 'qwen-saved'
            workflow_settings.save_flow(project, 'storyboard', draft, 'qwen')
            self.assertEqual(draft['engine'], 'qwen')
            loaded = workflow_settings.load(project, 'storyboard')
            self.assertEqual(loaded['engine'], 'qwen')
            self.assertEqual(loaded['profiles']['qwen']['model'], 'qwen-saved')
            self.assertEqual(workflow_settings.load(project, 'writing')['profiles']['qwen']['model'], 'qwen-saved')

    def test_save_flow_rejects_an_invalid_profile_before_writing(self):
        with tempfile.TemporaryDirectory() as project:
            draft = workflow_settings.defaults('storyboard')
            draft['profiles']['codex']['model'] = 'bad id'
            with self.assertRaisesRegex(ValueError, '模型 ID'):
                workflow_settings.save_flow(project, 'storyboard', draft, 'codex')
            self.assertFalse(workflow_settings.settings_path(project).exists())


if __name__ == '__main__':
    unittest.main()
