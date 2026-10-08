"""HOLLMWOOD 设置必须到达首次及续发 Agent 任务，不调用真实模型。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import codex_tasks
import stage_config
import workflow_settings
from workflow_engines import prompt_with_settings
from workflow_tasks import script_prompt, script_followup


class HollmwoodAgentDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)

    def configure(self, enabled=True, **rules):
        stage_config.put(self.project, 'script', hollmwood_enabled=enabled, **rules)
        return workflow_settings.current(self.project, 'writing')

    def prompts(self, config):
        with patch('workflow_tasks._agent_delivery_contract', return_value='正式交付路径'):
            initial = script_prompt(self.project, None, 'writing', creative_text='虚构素材', agent_delivery=True)
            followup = script_followup(None, 'writing', project=self.project, creative_text='追加素材', agent_delivery=True)
        return tuple(prompt_with_settings(p, config, stage='writing') for p in (initial, followup))

    def test_enabled_reaches_initial_and_followup_once(self):
        for prompt in self.prompts(self.configure()):
            self.assertIn('HOLLMWOOD 四角色协作：已启用', prompt)
            self.assertEqual(prompt.count('单窗口四阶段协作'), 1)
            for role in ('导演规划', '编剧初稿', '编辑改写', '演员润色'):
                self.assertIn(role, prompt)
            for text in ('节奏尺度按所选 SKILL', '对白字数按所选 SKILL',
                         '单集时长以简报的“单集时间”字段为准', 'APPROVED', 'REVISE:'):
                self.assertIn(text, prompt)
            for text in ('黄金 3 秒', '20 个汉字', '单句 20 字', '60–90',
                         'golden_three_seconds', 'conflict_escalation',
                         'scene_emotional_turn', 'ending_cliffhanger',
                         'dialogue_line_max_chars', 'episode_duration_seconds',
                         'Gate 1~2', 'Gate 3~5', '空泛情绪形容词'):
                self.assertNotIn(text, prompt)
            self.assertEqual(prompt.count('禁止结构化剧本'), 1)
            self.assertNotIn('全局节奏模板', prompt)
            self.assertNotIn('template_id:', prompt)
            self.assertNotIn('rules: {}', prompt)

    def test_blank_rhythm_does_not_inject_a_template_on_either_path(self):
        for template in ('  ', '# 空节奏配置', 'name: 占位\nrules: {}\nconstraints: {}'):
            with self.subTest(template=template):
                for prompt in self.prompts(self.configure(hollmwood_rhythm_template=template)):
                    self.assertNotIn('全局节奏模板', prompt)
                    self.assertNotIn('name: 占位', prompt)

    def test_disabled_cancels_prior_collaboration_on_both_paths(self):
        for prompt in self.prompts(self.configure(False)):
            self.assertIn('HOLLMWOOD 四角色协作：未启用', prompt)
            self.assertIn('不沿用历史四角色规则', prompt)
            self.assertNotIn('单窗口四阶段协作', prompt)
            self.assertNotIn('你是漫剧导演', prompt)

    def test_project_overrides_reach_both_paths_and_change_setup_snapshot(self):
        before = self.configure()
        after = self.configure(hollmwood_rhythm_template='自定义节奏甲',
                               hollmwood_director_rules='导演覆盖甲',
                               hollmwood_writer_rules='编剧覆盖甲',
                               hollmwood_editor_rules='编辑覆盖甲',
                               hollmwood_actor_rules='演员覆盖甲')
        self.assertNotEqual(json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True))
        for prompt in self.prompts(after):
            for text in ('自定义节奏甲', '导演覆盖甲', '编剧覆盖甲', '编辑覆盖甲', '演员覆盖甲'):
                self.assertEqual(prompt.count(text), 1)

    def test_disabled_changes_setup_snapshot(self):
        self.assertNotEqual(self.configure(), self.configure(False))

    def test_other_stages_do_not_receive_collaboration(self):
        config = self.configure()
        self.assertNotIn('HOLLMWOOD', prompt_with_settings('分镜任务', config, stage='storyboard'))

    def test_api_task_body_excludes_disabled_collaboration(self):
        self.configure(False)
        prompt = script_prompt(self.project, None, 'writing', creative_text='素材')
        self.assertNotIn('单窗口四阶段协作', prompt)
        self.assertNotIn('节奏模板', prompt)
        self.assertNotIn('HOLLMWOOD 四角色协作：未启用', prompt)

    def test_codex_visible_summary_and_file_contain_current_settings(self):
        class EmptyRPC:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def call(self, method, args): return {'data': [], 'nextCursor': None}

        config = self.configure()
        initial, followup = self.prompts(config)
        result = codex_tasks.prepare_task(
            self.project, '测试 剧本准备', 'writing', initial, rpc_factory=EmptyRPC,
            followup=followup, delivery_summary=workflow_settings.hollmwood_summary(config, 'writing'))
        self.assertIn('HOLLMWOOD 四角色协作：已启用', result['prompt'])
        self.assertIn('HOLLMWOOD 四角色协作：已启用', result['draft_prompt'])
        self.assertIn('导演规划', Path(result['task_file']).read_text(encoding='utf-8'))

    def test_reused_codex_thread_writes_current_disabled_followup(self):
        project = self.project
        rollout = project / 'rollout.jsonl'
        rollout.touch()

        class ExistingRPC:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def call(self, method, args):
                return {'data': [{'id': 'test-thread', 'name': '测试 剧本准备',
                                  'cwd': str(project), 'path': str(rollout)}], 'nextCursor': None}

        config = self.configure(False)
        initial, followup = self.prompts(config)
        result = codex_tasks.prepare_task(
            project, '测试 剧本准备', 'writing', initial, rpc_factory=ExistingRPC,
            followup=followup, delivery_summary=workflow_settings.hollmwood_summary(config, 'writing'))
        self.assertEqual(result['mode'], 'existing')
        self.assertIn('HOLLMWOOD 四角色协作：未启用', result['prompt'])
        delivered = Path(result['task_file']).read_text(encoding='utf-8')
        self.assertEqual(delivered, followup)
        self.assertIn('不沿用历史四角色规则', delivered)
        self.assertNotIn('单窗口四阶段协作', delivered)


if __name__ == '__main__':
    unittest.main()
