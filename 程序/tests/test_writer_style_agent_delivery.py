"""项目级编剧风格必须到达首次及续发 Agent 任务，不调用真实模型。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import codex_tasks
from agent.core import save
import stage_config
import workflow_settings
from workflow_engines import prompt_with_settings
from orchestrator.workflow_tasks import script_prompt, script_followup


class WriterStyleAgentDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)

    def configure(self, style=''):
        stage_config.put(self.project, 'script', writer_style=style)
        return workflow_settings.current(self.project, 'writing')

    def prompts(self, config):
        with patch('orchestrator.workflow_tasks._agent_delivery_contract', return_value='正式交付路径'):
            initial = script_prompt(self.project, None, 'writing', creative_text='虚构素材', agent_delivery=True)
            followup = script_followup(None, 'writing', project=self.project, creative_text='追加素材', agent_delivery=True)
        return tuple(prompt_with_settings(p, config, stage='writing') for p in (initial, followup))

    def test_style_reaches_initial_and_followup_once(self):
        for prompt in self.prompts(self.configure('参考好莱坞编剧，三幕清晰')):
            self.assertEqual(prompt.count('参考好莱坞编剧，三幕清晰'), 1)
            self.assertIn('本项目编剧风格', prompt)
            for obsolete in ('HOLLMWOOD', '单窗口四阶段协作', '你是漫剧导演', '全局节奏模板'):
                self.assertNotIn(obsolete, prompt)

    def test_blank_style_injects_nothing_on_either_path(self):
        for style in ('', '   '):
            with self.subTest(style=style):
                for prompt in self.prompts(self.configure(style)):
                    self.assertNotIn('本项目编剧风格', prompt)
                    self.assertNotIn('HOLLMWOOD', prompt)

    def test_style_changes_setup_snapshot(self):
        before = self.configure()
        after = self.configure('参考好莱坞编剧')
        self.assertNotEqual(json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True))

    def test_legacy_writer_rules_migrate_into_style_and_are_not_written_back(self):
        save(self.project / stage_config.CONFIG_NAME, {
            'script': {'model': 'auto', 'skills': [], 'hollmwood_writer_rules': '旧编剧规则',
                       'hollmwood_enabled': False, 'hollmwood_actor_rules': '旧演员规则'}})
        self.assertEqual(stage_config.writer_style(self.project), '旧编剧规则')
        stage_config.put(self.project, 'script', writer_style=stage_config.writer_style(self.project))
        saved = json.loads((self.project / stage_config.CONFIG_NAME).read_text(encoding='utf-8'))['script']
        self.assertEqual(saved['writer_style'], '旧编剧规则')
        self.assertFalse([key for key in saved if key.startswith('hollmwood')])

    def test_other_stages_do_not_receive_style(self):
        config = self.configure('参考好莱坞编剧')
        self.assertNotIn('参考好莱坞编剧', prompt_with_settings('分镜任务', config, stage='storyboard'))

    def test_api_task_body_excludes_style(self):
        self.configure('参考好莱坞编剧')
        prompt = script_prompt(self.project, None, 'writing', creative_text='素材')
        self.assertNotIn('参考好莱坞编剧', prompt)
        self.assertNotIn('HOLLMWOOD', prompt)

    def test_codex_visible_summary_and_file_contain_current_style(self):
        class EmptyRPC:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def call(self, method, args): return {'data': [], 'nextCursor': None}

        config = self.configure('参考好莱坞编剧')
        initial, followup = self.prompts(config)
        result = codex_tasks.prepare_task(
            self.project, '测试 剧本准备', 'writing', initial, rpc_factory=EmptyRPC,
            followup=followup, delivery_summary=workflow_settings.writer_style_summary(config, 'writing'))
        self.assertIn('编剧风格：已启用', result['prompt'])
        self.assertIn('编剧风格：已启用', result['draft_prompt'])
        self.assertIn('参考好莱坞编剧', Path(result['task_file']).read_text(encoding='utf-8'))

    def test_reused_codex_thread_writes_current_followup_without_style_when_cleared(self):
        project = self.project
        rollout = project / 'rollout.jsonl'
        rollout.touch()

        class ExistingRPC:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def call(self, method, args):
                return {'data': [{'id': 'test-thread', 'name': '测试 剧本准备',
                                  'cwd': str(project), 'path': str(rollout)}], 'nextCursor': None}

        config = self.configure('')
        initial, followup = self.prompts(config)
        result = codex_tasks.prepare_task(
            project, '测试 剧本准备', 'writing', initial, rpc_factory=ExistingRPC,
            followup=followup, delivery_summary=workflow_settings.writer_style_summary(config, 'writing'))
        self.assertEqual(result['mode'], 'existing')
        delivered = Path(result['task_file']).read_text(encoding='utf-8')
        self.assertEqual(delivered, followup)
        self.assertNotIn('本项目编剧风格', delivered)


if __name__ == '__main__':
    unittest.main()
