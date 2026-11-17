"""最终 Agent/API 拼装只带一份阶段契约，项目级编剧风格按配置注入。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import script_contract
import workflow_settings
import writing_api
from stage_execution_service import publish_stage_text
from workflow_engines import prompt_with_settings
from orchestrator.workflow_tasks import script_followup, script_prompt


class ScriptPromptAssemblyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.contract = workflow_settings.stage_output_contract('writing')
        self.assertTrue(self.contract)

    def test_agent_initial_and_followup_have_one_contract(self):
        with patch('orchestrator.workflow_tasks._agent_delivery_contract', return_value='正式交付路径'):
            initial = script_prompt(self.root, None, 'writing', creative_text='首发素材', agent_delivery=True)
            followup = script_followup(None, 'writing', project=self.root,
                                       creative_text='续发素材', agent_delivery=True)
        for engine in ('codex', 'claude'):
            for enabled in (False, True):
                config = {'engine': engine, 'writer_style': '测试编剧风格' if enabled else ''}
                for label, task in (('initial', initial), ('followup', followup)):
                    with self.subTest(engine=engine, enabled=enabled, message=label):
                        prompt = prompt_with_settings(task, config, stage='writing')
                        self.assertEqual(prompt.count(self.contract), 1)
                        self.assertEqual(prompt.count('测试编剧风格'), int(enabled))
                        self.assertNotIn('单窗口四阶段协作', prompt)
                        self.assertIn('正式交付路径', prompt)

    def test_agent_prompt_only_lists_changed_episode_numbers(self):
        from contract.stage_path_service import write_dir
        original = '# 第1集：起风\n第一集正文\n\n# 第2集：雨后\n第二集正文\n'
        folder = write_dir(self.root, 'script')
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / '项目_自然剧本_正稿_20261012.md'
        target.write_text(original, encoding='utf-8')
        with patch('orchestrator.workflow_tasks._agent_delivery_contract', return_value='正式交付路径'):
            first = script_prompt(self.root, None, 'writing', creative_text='素材', agent_delivery=True)
            script_contract.record_episode_ledger(self.root, original, previous_text='')
            target.write_text(original.replace('第二集正文', '第二集改过的正文'), encoding='utf-8')
            second = script_prompt(self.root, None, 'writing', creative_text='素材', agent_delivery=True)
        self.assertIn('尚无分集增量基线', first)
        self.assertNotIn('第二集正文', first)
        self.assertNotIn('第二集改过的正文', second)
        notice = next(line for line in second.splitlines() if line.startswith('【分集改动】'))
        self.assertIn('第2集', notice)
        self.assertNotIn('第1集', notice)

    def api_setup(self, style):
        import stage_config
        stage_config.put(self.root, 'script', model='test-model', skills=[], writer_style=style)
        brief = script_contract.brief_document({
            'story_summary': '修表师寻找父亲', 'main_characters': '林青与阿禾',
            'genre': '冒险', 'length': '12集，每集90秒'})
        for target, value in (
            ('writing_api.selected_model', ('test-model', {'context_length': 128000})),
            ('writing_api._complete_brief', brief),
            ('workflow_context.snapshot', {}),
            ('orchestrator.workflow_context_controller.publish_writing_context', '项目接续'),
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

    def test_direct_api_has_one_system_contract_and_no_noise(self):
        adapter, _brief = self.api_setup('')
        result = writing_api.reply(self.root, '本轮创意')
        adapter.chat.assert_called_once()
        messages = adapter.chat.call_args.args[0]
        system = adapter.chat.call_args.kwargs['system']
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['role'], 'user')
        self.assertEqual(system.count(self.contract), 1)
        self.assertEqual(messages[0]['content'].count(self.contract), 0)
        combined = system + messages[0]['content']
        self.assertEqual(combined.count(self.contract), 1)
        for obsolete in ('单窗口四阶段协作', '节奏模板', '本项目编剧风格'):
            self.assertNotIn(obsolete, combined)
        self.assertIn('本轮创意', combined)
        self.assertIn('<brief_complete>', combined)
        self.assertTrue(result['ok'])

    def test_direct_api_puts_writer_style_in_the_system_prompt_once(self):
        adapter, _brief = self.api_setup('参考好莱坞编剧')
        result = writing_api.reply(self.root, '本轮创意')
        adapter.chat.assert_called_once()
        system = adapter.chat.call_args.kwargs['system']
        user = adapter.chat.call_args.args[0][0]['content']
        self.assertEqual(system.count('参考好莱坞编剧'), 1)
        self.assertIn('本项目编剧风格', system)
        self.assertNotIn('参考好莱坞编剧', user)
        self.assertTrue(result['ok'])


if __name__ == '__main__':
    unittest.main()
