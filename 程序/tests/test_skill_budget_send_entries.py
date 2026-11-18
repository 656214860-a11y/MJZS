"""R3281: hermetic send/freeze -> CLI contract and real writing HTTP boundary.

CLI deliberately composes two contracts at _FlowAgentLaunch.prepare: real slash
parse/send/build/current/resolve/freeze, then the same frozen configuration through
real workflow_engines/qwen_adapter. This is not a complete Tk/UI dispatch test.
No installed skills, model pool, user configuration, secrets or remote API needed.
"""
import contextlib
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import desktop_shared_send as shared
import domain.skill_command as commands
import orchestrator.workflow_settings as settings
import orchestrator.workflow_engines as engines
import orchestrator.qwen_adapter as qwen
import writing_api
from contract.workflow_context_budget import estimate_tokens
from infra.model_router import PoolAdapter
from ui.desktop_idea_chat import _FlowAgentLaunch, _FlowAgentRequest


class SkillBudgetSendEntriesTests(unittest.TestCase):
    MODEL = 'deepseek-v4.1-flash-1017'
    URL = 'https://synthetic.invalid/v1'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.program = self.root / 'program'
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / 'skill_config.json').write_text('{}', encoding='utf-8')
        self.skills = self.program / 'skills'
        self.target = (self.skills / 'registered-packages' /
                       'short-drama-director' / 'SKILL.md')
        self.target.parent.mkdir(parents=True)
        self.target.write_text('---\nname: short-drama-director\n---\n目标入口正文', encoding='utf-8')
        self.paths, self.bodies = [], []
        # Conservative estimator charges ~2 tokens/Chinese character: ~58K total;
        # fully expanding references would exceed the 300000-character ceiling.
        for number in range(6):
            folder = self.skills / ('synthetic-%d' % number)
            folder.mkdir()
            body = 'BODY_SENTINEL_%d\n' % number + '正文' * 2400 + '\n[材料](reference.md)\nEND_SENTINEL_%d' % number
            path = folder / 'SKILL.md'
            path.write_text('---\nname: synthetic-%d\n---\n%s' % (number, body), encoding='utf-8')
            (folder / 'reference.md').write_text('引用资料' * 16000, encoding='utf-8')
            self.paths.append(path)
            self.bodies.append(body)
        self.registry = SimpleNamespace(getById=lambda key: None, disabled_names=lambda: [])

    def record(self, window=128000, model=None):
        return dict(model=model or self.MODEL, label='Synthetic DeepSeek', provider='DeepSeek',
                    base_url=self.URL, path='/chat/completions', wire_api='chat',
                    key_env='SYNTHETIC_TEST_KEY', context_length=window, rpm=60)

    @contextlib.contextmanager
    def isolated(self, record, model=None):
        model = model or self.MODEL
        profile = dict(program='', model=model, skill=str(self.paths[0]),
                       skills=list(map(str, self.paths)), instructions='')
        value = dict(engine='qwen', profiles={key: copy.deepcopy(profile) for key in settings.ENGINES})
        with contextlib.ExitStack() as stack:
            patches = [
                patch.object(settings, 'load', return_value=value),
                patch.object(settings, '_local_engine_for_selected_model', return_value=('', '')),
                patch.object(settings.skill_registry, 'skill_roots', return_value=[self.skills]),
                patch.object(settings.skill_registry, 'default_registry', return_value=self.registry),
                patch('infra.model_pool.pool', return_value={model: record}),
                patch('infra.stage_model_value.value', return_value=model),
                patch('orchestrator.stage_config.get', return_value={'model': model, 'skills': []}),
                patch('orchestrator.stage_config.workflow_lock', return_value={}),
                patch('orchestrator.stage_config.project_created_at', return_value=''),
                patch('orchestrator.stage_config.writer_style', return_value=''),
                patch.object(settings.edit_habits, 'config_fields', return_value={}),
            ]
            for item in patches:
                stack.enter_context(item)
            yield

    def assert_frozen(self, config):
        frozen = config['frozen_skill_prompt']
        for body in self.bodies:
            self.assertIn(body, frozen)
        self.assertEqual(len(config['skill_injection']['loaded']), 6)
        inline_budget = config['skill_injection']['inline_budget']
        if inline_budget is None:
            self.assertEqual(config['engine'], 'qwen')
            self.assertEqual(config['skill_budget']['context_length'], 0)
            self.assertEqual(config['skill_budget']['source'], 'unknown')
            self.assertLessEqual(len(frozen), 300_000)
            self.assertEqual(config['skill_injection']['skipped'], [])
        else:
            self.assertLessEqual(estimate_tokens(frozen), inline_budget)
            self.assertGreater(len('引用资料' * 16000) * 6, 300000)
            self.assertTrue(config['skill_injection']['skipped'])

    def command_to_frozen(self, rejection=''):
        captured = []
        host = SimpleNamespace(root=self.project, worker=None, status=Mock(), notifier=Mock(),
                               projects=SimpleNamespace(info={'projects': []}),
                               async_=lambda task, callback: task(),
                               account_stage_gate=lambda stage: '', draft_text=lambda: '合成任务')
        def open_flow(stage, label, prompt):
            request = _FlowAgentRequest(stage, label, prompt, None, None, None, False, False, False)
            return _FlowAgentLaunch(host, request).build()
        host.open_flow_agent = open_flow
        def prepared(launch):
            captured.append((launch.config, launch.prompt))
            return captured[-1]
        raw = '/short-drama-director 继续合成任务'
        parsed = commands.parse_command(raw, stage='script', skills=[], engines=['short-drama-director'])
        self.assertEqual(parsed['kind'], 'engine')
        with patch.object(shared, '_skill_items', return_value=[SimpleNamespace(
                name='short-drama-director', stage='script', path=self.target, layer='user')]), \
                patch.object(_FlowAgentLaunch, 'prepare', prepared):
            accepted = shared.send(host, 'script', raw, parsed)
        if rejection:
            self.assertFalse(accepted)
            self.assertEqual(captured, [])
            self.assertIn(rejection, str(host.notifier.error.call_args))
            return
        self.assertTrue(accepted, host.notifier.error.call_args or host.status.set.call_args)
        self.assertEqual(len(captured), 1)
        config, prompt = captured[0]
        self.assertIn(str(self.target), prompt)
        self.assertNotIn('BODY_SENTINEL_', prompt)  # _skill_prompt is path-only.
        self.assertEqual(config['engine'], 'qwen')
        self.assert_frozen(config)
        return config, prompt

    def launch_frozen(self, config, prompt):
        process = SimpleNamespace(pid=987654, poll=lambda: None)
        full_prompt = engines.prompt_with_settings(prompt, config, stage='writing')
        with patch.object(engines, 'reserve_stage_process_slot', return_value='synthetic-slot'), \
                patch.object(qwen, 'command', return_value=['synthetic-qwen.exe']), \
                patch('infra.qwen_setup.load', return_value={
                    'base_url': 'https://unused.invalid/v1', 'model': 'unused', 'api_key': 'synthetic-only'}), \
                patch('infra.qwen_setup.api_credential', return_value='synthetic-only'), \
                patch.object(qwen, 'launch_windows_app', return_value=process) as launch, \
                patch.object(qwen.executors, 'submit') as executor_submit, \
                patch('infra.workflow_process_registry.register_process'):
            result = engines.launch_interactive(self.project, 'writing', '合成任务', full_prompt, config,
                                                new_session=True)
        self.assertEqual(launch.call_count, 1)
        args = launch.call_args.kwargs['args']
        self.assertEqual(args[args.index('--model') + 1], self.MODEL)
        self.assertEqual(launch.call_args.kwargs['env']['OPENAI_BASE_URL'], self.URL)
        self.assertTrue(executor_submit.called)  # ready/title worker submitted via executors.
        task = Path(result['task_file']).read_text(encoding='utf-8')
        for body in self.bodies:
            self.assertIn(body, task)
        return result

    def test_cli_raw_engine_command_reaches_qwen_task_with_explicit_128k(self):
        with self.isolated(self.record()):
            config, prompt = self.command_to_frozen()
            self.launch_frozen(config, prompt)

    def test_cli_unknown_window_still_delivers_complete_task(self):
        # Full references also fit the independent 300K character hard limit.
        for path in self.paths:
            (path.parent / 'reference.md').write_text('合成引用正文', encoding='utf-8')
        with self.isolated(self.record('')):
            config, prompt = self.command_to_frozen()
            self.launch_frozen(config, prompt)
        self.assertIn('合成引用正文', config['frozen_skill_prompt'])
        self.assertEqual(config['skill_budget']['context_length'], 0)
        self.assertEqual(config['skill_budget']['source'], 'unknown')

    def test_cli_unknown_window_keeps_character_hard_limit(self):
        with self.isolated(self.record('')), patch.object(qwen, 'launch_windows_app') as launch:
            self.command_to_frozen(rejection='300,000')
        launch.assert_not_called()

    def test_registered_skill_has_priority_and_space_command_is_free_text(self):
        raw = '/short-drama-director'
        parsed = commands.parse_command(raw, stage='script', skills=['short-drama-director'],
                                        engines=['short-drama-director'])
        self.assertEqual(parsed['kind'], 'skill')
        spaced = '/short drama director'
        self.assertIsNone(commands.parse_command(spaced, stage='script', skills=[],
                                                engines=['short-drama-director']))
        host = SimpleNamespace(send_message=Mock(return_value=True))
        self.assertTrue(shared.send(host, 'script', spaced, None))
        host.send_message.assert_called_once_with()  # send_message reads its existing input widget.

    def test_cli_huge_bodies_stop_before_launch(self):
        for path in self.paths:
            path.write_text('正文' * 30000, encoding='utf-8')
        with self.isolated(self.record()), patch.object(qwen, 'launch_windows_app') as launch:
            self.command_to_frozen(rejection='正文')
        launch.assert_not_called()

    def api_exchange(self, record, model=None):
        model = model or self.MODEL
        calls = []
        def transport(url, payload, headers, timeout):
            calls.append((url, payload))
            return {'ok': True, 'status': 200, 'data': {
                'id': 'synthetic-response', 'object': 'chat.completion', 'model': model,
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': '已收到合成任务'},
                             'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 60000, 'completion_tokens': 10, 'total_tokens': 60010}}}
        def adapter(item, chosen, **kwargs):
            return PoolAdapter(item, chosen, program=self.program, key='synthetic-only', transport=transport)
        with self.isolated(record, model), \
                patch.object(writing_api, 'PoolAdapter', side_effect=adapter), \
                patch.object(writing_api, '_complete_brief', return_value=None), \
                patch('domain.idea_transcript.load', return_value=[]), \
                patch.object(writing_api, '_record_model_diagnostic'), \
                patch('domain.workflow_context.snapshot', return_value={}), \
                patch('orchestrator.project_context_factory.project_context', return_value=object()), \
                patch('orchestrator.workflow_context_controller.publish_writing_context', return_value='合成上下文'), \
                patch('orchestrator.workflow_tasks.script_prompt', return_value='合成任务'), \
                patch('infra.model_pool.wait_for_rpm') as rpm:
            try:
                request = writing_api.capture_request(self.project)
                self.assert_frozen(request['settings'])
                result = writing_api.reply(self.project, '开始合成任务', request_model=request)
            except ValueError as exc:
                return calls, None, str(exc), rpm.call_count
        return calls, result, '', rpm.call_count

    def test_api_capture_reply_real_pool_transport_explicit_128k(self):
        self.assert_api_success(self.record())

    def test_api_unknown_same_model_stops_before_transport_and_rpm(self):
        calls, result, error, rpm = self.api_exchange(self.record(''))
        self.assertEqual(calls, [])
        self.assertEqual(rpm, 0)
        self.assertIn('context_window_unknown', error or result.get('reason', ''))
        self.assertIn('context_length', error or result.get('error', ''))

    def assert_api_success(self, record):
        calls, result, error, rpm = self.api_exchange(record)
        self.assertEqual(error, '')
        self.assertTrue(result['ok'], result)
        self.assertEqual(len(calls), 1)
        self.assertEqual(rpm, 1)
        url, payload = calls[0]
        self.assertEqual(url, self.URL + '/chat/completions')
        self.assertEqual(payload['model'], self.MODEL)
        system = next(item['content'] for item in payload['messages'] if item['role'] == 'system')
        for body in self.bodies:
            self.assertIn(body, system)

    def test_api_unknown_window_stops_before_http_or_rpm(self):
        calls, result, error, rpm = self.api_exchange(self.record('', 'synthetic-unknown'), 'synthetic-unknown')
        self.assertIn('未填写上下文窗口', error)
        self.assertEqual((calls, result, rpm), ([], None, 0))

    def test_api_huge_bodies_stop_before_http_or_rpm(self):
        for path in self.paths:
            path.write_text('正文' * 30000, encoding='utf-8')
        calls, result, error, rpm = self.api_exchange(self.record())
        self.assertIn('正文', error)
        self.assertEqual((calls, result, rpm), ([], None, 0))


if __name__ == '__main__':
    unittest.main()
