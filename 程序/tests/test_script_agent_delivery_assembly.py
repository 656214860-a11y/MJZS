"""最终 Agent/API 拼装只带一份阶段契约，四角色规则按开关注入。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import script_contract
import workflow_settings
import writing_api
from service_contract import success
from workflow_engines import prompt_with_settings
from workflow_tasks import script_followup, script_prompt


class ScriptPromptAssemblyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.contract = workflow_settings.stage_output_contract('writing')
        self.assertTrue(self.contract)

    def test_agent_initial_and_followup_have_one_contract(self):
        with patch('workflow_tasks._agent_delivery_contract', return_value='正式交付路径'):
            initial = script_prompt(self.root, None, 'writing', creative_text='首发素材', agent_delivery=True)
            followup = script_followup(None, 'writing', project=self.root,
                                       creative_text='续发素材', agent_delivery=True)
        for engine in ('codex', 'claude'):
            for enabled in (False, True):
                config = {'engine': engine, 'hollmwood': {
                    'enabled': enabled, 'rhythm': '测试节奏', 'roles': {}}}
                for label, task in (('initial', initial), ('followup', followup)):
                    with self.subTest(engine=engine, enabled=enabled, message=label):
                        prompt = prompt_with_settings(task, config, stage='writing')
                        self.assertEqual(prompt.count(self.contract), 1)
                        self.assertEqual(prompt.count('单窗口四阶段协作'), int(enabled))
                        self.assertEqual(prompt.count('全局节奏模板（每个角色都必须遵守）：\n测试节奏'), int(enabled))
                        self.assertIn('正式交付路径', prompt)

    def api_setup(self, enabled):
        brief = script_contract.brief_document({
            'story_summary': '修表师寻找父亲', 'main_characters': '林青与阿禾',
            'genre': '冒险', 'length': '12集，每集90秒'})
        for target, value in (
            ('writing_api.selected_model', ('test-model', {})),
            ('workflow_settings.load', {}),
            ('writing_api._complete_brief', brief),
            ('stage_config.hollmwood_enabled', enabled),
            ('workflow_context.snapshot', {}),
            ('workflow_context_controller.publish_writing_context', '项目接续'),
            ('idea_chat.load', []),
            ('writing_api.model_label', '测试 API'),
            ('writing_api._context_budget_error', None),
            ('writing_api._record_model_diagnostic', None),
        ):
            self.enterContext(patch(target, return_value=value))
        # 本组只检验自然剧本阶段的最终拼装；前置确认的真实路由由 test_writing_api 覆盖。
        self.confirmed = {stage: stage + '已确认正文' for stage in writing_api.PREPARATION_STAGES}
        self.enterContext(patch('writing_api._preparation_step', return_value=(None, self.confirmed)))
        adapter = self.enterContext(patch('writing_api.PoolAdapter')).return_value
        adapter.wire_api = 'chat/completions'
        adapter.chat.return_value = {'ok': True, 'text': '短回复，不触发自动落盘'}
        return adapter, brief

    def test_direct_api_without_four_roles_has_one_system_contract_and_no_noise(self):
        adapter, _brief = self.api_setup(False)
        with patch('writing_api._hollmwood_reply') as four_roles:
            result = writing_api.reply(self.root, '本轮创意')
        four_roles.assert_not_called()
        adapter.chat.assert_called_once()
        messages = adapter.chat.call_args.args[0]
        system = adapter.chat.call_args.kwargs['system']
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['role'], 'user')
        self.assertEqual(system.count(self.contract), 1)
        self.assertEqual(messages[0]['content'].count(self.contract), 0)
        combined = system + messages[0]['content']
        self.assertEqual(combined.count(self.contract), 1)
        self.assertNotIn('单窗口四阶段协作', combined)
        self.assertNotIn('节奏模板', combined)
        self.assertIn('本轮创意', combined)
        self.assertIn('<brief_complete>', combined)
        self.assertTrue(result['ok'])

    def test_enabled_api_still_uses_roles_run_with_rhythm_and_rules(self):
        adapter, brief = self.api_setup(True)
        role_rules = {'writer': '测试编剧规则'}
        with patch('stage_config.hollmwood_rules', return_value=('测试节奏', '测试导演规则')), \
             patch('stage_config.hollmwood_role_rules', return_value=role_rules), \
             patch('hollmwood_roles.run', return_value=success({'script': '演员稿'})) as run, \
             patch('workflow_settings.skill_prompt', return_value='所选共享 SKILL 标记') as skill, \
             patch('writing_api._write_script_raw', return_value=self.root / 'script_raw.md') as publish, \
             patch('workflow_tasks.script_prompt') as plain_task:
            result = writing_api.reply(self.root, '本轮创意')
        plain_task.assert_not_called()
        adapter.chat.assert_not_called()
        run.assert_called_once()
        self.assertIs(run.call_args.args[0], adapter)
        self.assertEqual(run.call_args.args[1], 'test-model')
        self.assertEqual(run.call_args.args[2], dict(brief, 已确认阶段文件=self.confirmed, 本轮补充素材='本轮创意'))
        self.assertEqual(run.call_args.kwargs['rhythm_template'], '测试节奏')
        self.assertEqual(run.call_args.kwargs['director_rules'], '测试导演规则')
        self.assertEqual(run.call_args.kwargs['role_rules'], role_rules)
        self.assertEqual(run.call_args.kwargs['skill_instructions'], '所选共享 SKILL 标记')
        self.assertEqual(run.call_args.kwargs['output_contract'], self.contract
                         + '\n程序已核验设定、大纲、角色卡逐项确认；当前仅执行阶段④自然剧本，沿用简报中的已确认阶段文件。')
        self.assertTrue(skill.call_args.kwargs['inline'])
        publish.assert_called_once()
        self.assertTrue(result['ok'])
        self.assertTrue(result['hollmwood_enabled'])
        self.assertEqual(result['text'], '演员稿')


if __name__ == '__main__':
    unittest.main()
