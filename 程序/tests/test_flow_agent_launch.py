# -*- coding: utf-8 -*-
"""打开 Agent 任务（_FlowAgentLaunch）：剧本阶段的前置校验与新会话判定、Qwen 窗口标题、
Codex 技能同步失败、白模预演打开 Blender 并粘贴到 GPT 桌面、重复任务的重试与复用、
Qwen 续发、排队取槽被拒、全自动下的 Claude Desktop 提示。外部入口全部打桩，不启动进程。"""
import contextlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


def desktop_class():
    import importlib
    return importlib.import_module('desktop').Desktop


class _Proc:
    def poll(self):
        return None


class _AnyLiveSession(dict):
    """任何键都对应一个仍在运行的 Agent 进程。"""

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return _Proc()


class FlowAgentLaunchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / '项目'
        self.project.mkdir()
        self.timers = []

    def host(self, *, sync=True, **extra):
        def run(fn, done=None):
            value = fn()
            return done(value) if done else value
        win = Mock()
        win.after.side_effect = lambda ms, callback: self.timers.append(callback) or 'timer'
        values = dict(root=self.project, worker=False, win=win, status=Mock(), notifier=Mock(),
                      projects=SimpleNamespace(info={'projects': [{'name': '样片', 'path': str(self.project)}]}),
                      async_=run if sync else Mock(), gate_level=lambda: 'manual',
                      open_flow_agent=Mock(), update_script_interrupt_button=Mock())
        values.update(extra)
        return SimpleNamespace(**values)

    @contextlib.contextmanager
    def stubs(self, claim=None, **extra):
        self.finish = Mock()
        self.outcome = Mock()
        self.paste = Mock(return_value={'ok': True, 'reason': '已粘贴'})
        targets = {
            'agent_dispatch.claim': Mock(return_value=claim or {'duplicate': False}),
            'agent_dispatch.finish': self.finish,
            'agent_dispatch.outcome': self.outcome,
            'agent_dispatch.signature': Mock(return_value='sig'),
            'workflow_context.snapshot': Mock(return_value={}),
            'workflow_context.continuation_instruction': Mock(return_value=''),
            'orchestrator.workflow_context_controller.request_stage_instruction': Mock(return_value=('', 'stage')),
            'contract.workflow_context_budget.prepare_request_context': lambda text, *a, **k: (text, {}),
            'workflow_engines.prompt_with_settings': lambda prompt, config, stage: prompt,
            'orchestrator.agent_skill_sync.sync_agent_skills': Mock(
                return_value={'errors': [], 'conflicts': []}),
            'prompt_window.copy_text': Mock(),
            'codex_paste.paste_existing': self.paste,
            'contract.platform_tools.launch_windows_app': Mock(),
        }
        targets.update(extra)
        with contextlib.ExitStack() as stack:
            for target, value in targets.items():
                stack.enter_context(patch(target, value))
            yield

    def open(self, host, stage, config=None, **kwargs):
        desktop_class().open_flow_agent(host, stage, '任务', '请执行', _config=config, **kwargs)

    def test_writing_validates_skills_and_restarts_a_stale_claude_session(self):
        host = self.host(sync=False)
        config = {'engine': 'claude', 'program': '', 'model': ''}
        with self.stubs(), \
                patch('workflow_settings.validate_selected_skills') as validate, \
                patch('workflow_settings.current', return_value=config), \
                patch('workflow_settings.freeze_skills', side_effect=lambda value: value), \
                patch('workflow_engines.claude_session_stale', return_value=True) as stale:
            self.open(host, 'writing')
        validate.assert_called_once_with(self.project, 'writing')
        stale.assert_called_once_with(self.project, 'writing')
        launch = host.async_.call_args.args[0].__self__
        self.assertTrue(launch.new_session)
        self.assertEqual('样片 任务', launch.title)

    def test_qwen_uses_its_own_window_title(self):
        host = self.host(sync=False, page_index=3)
        with self.stubs(), patch('orchestrator.qwen_adapter.window_title', return_value='Qwen·样片') as title:
            self.open(host, 'storyboard', {'engine': 'qwen', 'program': '', 'model': ''})
        title.assert_called_once_with('样片', 'storyboard', 3)
        self.assertEqual('Qwen·样片', host.async_.call_args.args[0].__self__.title)

    def test_codex_skill_sync_problems_stop_before_claiming(self):
        host = self.host()
        sync = {'errors': ['缺技能'], 'conflicts': ['重名']}
        with self.stubs(), \
                patch('orchestrator.agent_skill_sync.sync_agent_skills', return_value=sync), \
                self.assertRaisesRegex(ValueError,
                    '^Agent 技能同步未完成：Codex：缺技能; Codex：重名; Agents：缺技能; Agents：重名$'):
            self.open(host, 'storyboard', {'engine': 'codex', 'program': '', 'model': ''})
        self.finish.assert_not_called()

    def test_previs_opens_blender_then_pastes_into_gpt_desktop(self):
        host = self.host()
        config = {'engine': 'codex', 'program': '', 'model': '', 'desktop_program': 'Codex.exe'}
        task = {'url': 'codex://new', 'title': '样片 任务', 'mode': 'new', 'prompt': '全文'}
        with self.stubs(), \
                patch('orchestrator.agent_skill_sync.sync_agent_skills',
                      return_value={'errors': [], 'conflicts': []}), \
                patch('native_apps.open_blender') as blender, \
                patch('codex_tasks.prepare_task', return_value=task) as prepare, \
                patch('desktop_idea_chat.open_target') as target, \
                patch('contract.platform_tools.launch_windows_app') as launch:
            self.open(host, 'previs', config)
        blender.assert_called_once_with()
        self.assertEqual('previs', prepare.call_args.args[2])
        self.assertEqual({'initial': {}, 'continuation': {}}, task['context_budget'])
        launch.assert_called_once_with('Codex.exe', 'Codex 桌面')
        target.assert_called_once_with('codex://new')
        self.assertEqual(45, self.paste.call_args.kwargs['deadline_seconds'])
        self.assertEqual(('prepared', '已粘贴'), self.finish.call_args.args[1:3])
        host.status.set.assert_called_with('正在将本次任务粘贴到 GPT 桌面，请在窗口中手动点击发送…')

    def test_duplicate_task_retries_when_safe_or_is_reused_while_alive(self):
        config = {'engine': 'claude', 'program': '', 'model': ''}
        duplicate = {'duplicate': True, 'state': 'sent'}
        host = self.host(flow_processes=_AnyLiveSession())
        with self.stubs(claim=duplicate), patch('agent_dispatch.retryable', return_value=True):
            self.open(host, 'storyboard', config)
        self.assertEqual('上次发送结果未确认，且对应 Agent 窗口已关闭', self.finish.call_args.args[2])
        host.status.set.assert_called_once_with('上次 Agent 发送未确认且窗口已关闭，正在自动重新启动…')
        self.assertEqual(config, host.open_flow_agent.call_args.kwargs['_config'])
        host = self.host(flow_processes=_AnyLiveSession())
        with self.stubs(claim=duplicate), patch('agent_dispatch.retryable', return_value=False):
            self.open(host, 'storyboard', config)
        host.status.set.assert_called_once_with('相同任务已发送，已复用记录，本次不重复发送。请在对应 Agent 窗口继续。')
        host.open_flow_agent.assert_not_called()

    def test_live_qwen_session_gets_the_followup(self):
        host = self.host(flow_processes=_AnyLiveSession())
        with self.stubs(), patch('orchestrator.qwen_adapter.window_title', return_value='Q'), \
                patch('orchestrator.qwen_adapter.submit_existing', return_value='已续发') as submit:
            self.open(host, 'storyboard', {'engine': 'qwen', 'program': '', 'model': ''})
        self.assertEqual(('请执行',), submit.call_args.args[1:])
        self.assertEqual({'ok': True, 'reason': '已续发', 'send_dispatched': True}, self.outcome.call_args.args[1])
        host.status.set.assert_called_with('已续发')

    def test_queued_request_reports_position_then_rejection(self):
        host = self.host()
        claims = iter([{'state': 'queued', 'position': 1}, {'state': 'rejected', 'reason': '并发名额已满'}])
        with self.stubs(), \
                patch('workflow_engines.request_stage_process_slot',
                      return_value={'state': 'queued', 'ticket': 'T', 'position': 2}), \
                patch('workflow_engines.claim_stage_process_slot', side_effect=lambda ticket: next(claims)), \
                patch('workflow_engines.cancel_stage_slot_request') as cancel:
            self.open(host, 'storyboard', {'engine': 'claude', 'program': '', 'model': ''})
            self.timers.pop(0)()
            self.timers.pop(0)()
        self.assertEqual([], self.timers)
        cancel.assert_called_once_with('T')
        self.assertEqual([c.args[0] for c in host.status.set.call_args_list],
                         ['模型请求排队中（第2位），尚未启动 CLI；可点击中断，最多等待 120 秒。',
                          '模型请求排队中（第1位），尚未启动 CLI；可点击中断，最多等待 120 秒。',
                          '并发名额已满'])
        self.assertEqual(('failed', '并发名额已满'), self.finish.call_args.args[1:3])

    def test_full_auto_tells_the_user_to_send_in_claude_desktop(self):
        host = self.host(gate_level=lambda: 'auto')
        task_file = self.project / '任务.md'
        with self.stubs(), patch('codex_tasks.task_file_reference', return_value=task_file), \
                patch('stage_execution_service.register_download_inbox'), \
                patch('workflow_settings.find_program', return_value='Claude.exe'):
            self.open(host, 'storyboard', {'engine': 'claude-desktop-app', 'program': '', 'model': ''})
        message = ('三虎全自动：任务 的任务已粘贴到 Claude Desktop，'
                   '请切到 Claude Desktop 手动点击发送；完成后产物会自动收回。')
        host.status.set.assert_called_with(message)
        host.notifier.warning.assert_called_once_with(message, title='请手动发送')

    def test_skill_send_api_route_api_model_never_opens_cli(self):
        """REQ-S01-118：接口模型（config['api'] 非空）在 open_flow_agent 任何入口都不起 CLI。"""
        api = {'base_url': 'https://x', 'path': '/v1', 'wire_api': 'chat', 'key_env': 'K'}
        for stage in ('assets', 'writing', 'video_prompt'):
            host = self.host(sync=False)
            config = {'engine': 'qwen', 'program': '', 'model': 'm1', 'api': api}
            with self.subTest(stage=stage), self.stubs(), \
                    patch('workflow_settings.freeze_skills', side_effect=lambda value: value):
                self.open(host, stage, config)
            host.async_.assert_not_called()
            host.status.set.assert_called_once_with('接口模型不使用命令行窗口')

    def test_skill_send_api_route_cli_model_unchanged(self):
        """REQ-S01-118：命令行引擎模型（无 api）行为逐字不变，照旧进入 use_cli 准备链。"""
        host = self.host(sync=False)
        with self.stubs():
            self.open(host, 'assets', {'engine': 'qwen', 'program': '', 'model': ''})
        host.async_.assert_called_once()
        self.assertEqual([], host.status.set.call_args_list)


class SkillSendApiRouteTests(unittest.TestCase):
    """REQ-S01-118（UX-B2API）：剧本页 /技能名 在接口模型下走应用内请求，不开命令行窗口。"""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / '项目'
        self.project.mkdir()

    def host(self, **extra):
        from orchestrator.idea_chat_controller import IdeaChatController
        values = dict(root=self.project, worker=False, status=Mock(), notifier=Mock(),
                      idea_chat_controller=IdeaChatController(),
                      open_flow_agent=Mock(), update_script_interrupt_button=Mock(),
                      set_idea_model_filter=Mock(), discard_idea_draft=Mock(),
                      show_conversation=Mock(), show_thinking=Mock(), begin_stream=Mock(),
                      stream_call=Mock(return_value={'ok': True, 'response_text': '好'}),
                      submit_idea_api_request=Mock(),
                      idea_chat_context=Mock(return_value=object()),
                      idea_chat_gateway=Mock(return_value={}))
        values.update(extra)
        return SimpleNamespace(**values)

    def request_model(self, label='M1'):
        from domain.idea_document_paths import ChatModel
        return {'id': 'm1', 'record': {'context_length': 128000},
                'label': ChatModel(label, 'm1', 'P'), 'provider': 'P'}

    def patches(self, settings=None, error=None):
        """send_skill_request 的外部边界全部打桩；settings 为 resolve_for_send 的返回。"""
        request = self.request_model()
        resolve = Mock()
        if error is not None:
            resolve.side_effect = error
        else:
            resolve.return_value = settings if settings is not None else {'skill_injection': {}}
        return (patch('writing_api.capture_request_model', return_value=request),
                patch('orchestrator.workflow_settings.resolve_for_send', resolve),
                patch('domain.idea_chat.append'), request, resolve)

    def send_skill(self, host, name='分镜技法', path=None, rest='做三版'):
        import desktop_shared_send as shared_send
        return shared_send.send_skill_request(
            host, name, path if path is not None else Path('skills') / 'x' / '分镜技法.skill.md', rest)

    def test_skill_send_api_route_shared_send_prefers_in_app_request(self):
        """剧本页 /技能名：send_skill_request 受理时不再 _open_flow 开命令行窗口。"""
        import desktop_shared_send as shared_send
        skill = SimpleNamespace(name='分镜技法', stage='storyboard',
                                path=Path('skills') / 'x' / '分镜技法.skill.md')
        desktop = self.host(opened=[],
                            shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        desktop.open_flow_agent = lambda *a, **k: desktop.opened.append(a)
        parsed = {'kind': 'skill', 'name': '分镜技法', 'stage': 'script', 'rest': '做三版'}
        with patch.object(shared_send, 'send_skill_request', return_value=True) as sender:
            self.assertTrue(shared_send.send(desktop, 'script', '/分镜技法 做三版', parsed))
        sender.assert_called_once_with(desktop, '分镜技法', skill.path, '做三版')
        self.assertEqual(desktop.opened, [])

    def test_skill_send_api_route_shared_send_falls_back_for_cli(self):
        """send_skill_request 返回 False（非接口模型）：原 _open_flow 链逐字保留。"""
        import desktop_shared_send as shared_send
        skill = SimpleNamespace(name='分镜技法', stage='storyboard',
                                path=Path('skills') / 'x' / '分镜技法.skill.md')
        desktop = self.host(opened=[],
                            shared_input=SimpleNamespace(skill_items=lambda: [skill]))
        desktop.open_flow_agent = lambda *a, **k: desktop.opened.append(a)
        parsed = {'kind': 'skill', 'name': '分镜技法', 'stage': 'script', 'rest': '做三版'}
        with patch.object(shared_send, 'send_skill_request', return_value=False):
            self.assertTrue(shared_send.send(desktop, 'script', '/分镜技法 做三版', parsed))
        self.assertEqual(desktop.opened[0][:2], ('writing', '剧本准备'))
        self.assertIn('请完整读取并严格遵循本地技能文件', desktop.opened[0][2])

    def test_skill_send_api_route_request_freezes_named_skill_in_app(self):
        """接口模型：只把本条点名技能冻结后装进应用内请求，请求链与自由文本一致。"""
        host = self.host()
        capture, resolve, append, request, resolver = self.patches({'skill_injection': {'loaded': []}})
        with capture, resolve, append as rows:
            self.assertTrue(self.send_skill(host))
        self.assertEqual(True, resolver.call_args.kwargs['direct_api'])
        self.assertEqual(('m1', {'context_length': 128000}), resolver.call_args.kwargs['model_snapshot'])
        config = {'stage_skills': ['a', 'b'], 'skills': ['x'], 'skill': 'x',
                  'engine': 'codex', 'model': '', 'invocation_mode': ''}
        resolver.call_args.kwargs['adjust'](config)
        self.assertEqual(config['stage_skills'], [str(Path('skills') / 'x' / '分镜技法.skill.md')])
        self.assertEqual(config['skills'], [])
        self.assertEqual(config['skill'], '')
        self.assertTrue(config['named_execution'])
        self.assertEqual(config['named_skills'], ['分镜技法'])
        self.assertEqual(config['engine'], 'qwen')
        self.assertEqual(config['invocation_mode'], 'api')
        self.assertEqual(config['model'], 'm1')
        user_rows = [c for c in rows.call_args_list if c.args[1] == 'user']
        self.assertEqual(len(user_rows), 1)
        self.assertEqual(user_rows[0].args[2], '/分镜技法 做三版')
        self.assertEqual(user_rows[0].kwargs['skill_injection'], {'loaded': []})
        host.submit_idea_api_request.assert_called_once()
        ask = host.submit_idea_api_request.call_args.args[3]
        ask()
        call = host.stream_call.call_args
        self.assertEqual(call.args[0].__name__, 'reply_to_writing')
        self.assertEqual(call.args[1:], (self.project, '做三版'))
        self.assertEqual(call.kwargs['user_message'], '/分镜技法 做三版')
        self.assertIs(call.kwargs['request_model'], request)
        self.assertTrue(host.idea_chat_controller.requesting)
        host.open_flow_agent.assert_not_called()

    def test_skill_send_api_route_degraded_reference_notice(self):
        """引用被省略或不可发送：照常发送已装下部分，notice＋状态栏各说明一次。"""
        cases = (
            ({'references': [{'status': 'skipped'}], 'skipped': [{'status': 'skipped'}],
              'degraded': True}, ['技能引用装不下本次请求，已省略部分引用']),
            ({'references': [{'status': 'resource'}], 'skipped': [], 'degraded': False},
             ['技能含无法随请求发送的文件，已省略']),
        )
        for injection, expected in cases:
            with self.subTest(injection=injection):
                host = self.host()
                capture, resolve, append, request, resolver = self.patches({'skill_injection': injection})
                with capture, resolve, append as rows:
                    self.assertTrue(self.send_skill(host))
                notice_rows = [c.args[2] for c in rows.call_args_list if c.args[1] == 'notice']
                self.assertEqual(notice_rows, expected)
                for text in expected:
                    host.status.set.assert_any_call(text)
                host.submit_idea_api_request.assert_called_once()

    def test_skill_send_api_route_refusal_explains_reason(self):
        """正文装不下或模型没填上下文长度：不发送，两处说明具体原因类别。"""
        cases = (
            (ValueError('未填写上下文窗口m1 context_window_unknown 填context_length'),
             '模型没有填上下文长度，请在模型管理里补充'),
            (ValueError('SKILL/阶段指令超出预算：完整正文及包装 9,999 token，预算 1,000 token，已阻止发送。'),
             '技能正文超出模型上下文'),
        )
        for error, expected in cases:
            with self.subTest(error=str(error)):
                host = self.host()
                capture, resolve, append, request, resolver = self.patches(error=error)
                with capture, resolve, append as rows:
                    self.assertTrue(self.send_skill(host))
                notice_rows = [c.args[2] for c in rows.call_args_list if c.args[1] == 'notice']
                self.assertEqual(notice_rows, [expected])
                host.status.set.assert_any_call(expected)
                host.submit_idea_api_request.assert_not_called()
                self.assertFalse(host.idea_chat_controller.requesting)

    def test_skill_send_api_route_non_api_model_returns_false(self):
        """非接口模型返回 False，由共享发送回落到原命令行链，不发应用内请求。"""
        host = self.host()
        request = {'id': '', 'record': {}, 'label': '', 'provider': ''}
        with patch('writing_api.capture_request_model', return_value=request):
            self.assertFalse(self.send_skill(host))
        host.submit_idea_api_request.assert_not_called()

    def test_skill_send_api_route_notice_stays_out_of_model_context(self):
        """notice 行只作显示：load(model) 拼上下文与 latest_text 都不含它；「全部」视图仍可见。"""
        from stage_execution_service import idea_chat_gateway, project_context
        import domain.idea_chat as idea_chat
        context = project_context(self.project)
        gateway = idea_chat_gateway()
        idea_chat.append(context, 'user', '问一句', model='测试模型UXB2API', gateway=gateway)
        idea_chat.append(context, 'assistant', '回一句', model='测试模型UXB2API', gateway=gateway)
        idea_chat.append(context, 'notice', '技能引用装不下本次请求，已省略部分引用',
                         model='测试模型UXB2API', gateway=gateway)
        model_rows = idea_chat.load(context, model='测试模型UXB2API', gateway=gateway)
        self.assertEqual([row['role'] for row in model_rows], ['user', 'assistant'])
        all_rows = idea_chat.load(context, model='', gateway=gateway)
        self.assertEqual([row['role'] for row in all_rows], ['user', 'assistant', 'notice'])
        self.assertNotIn('技能引用装不下', idea_chat.history_context(model_rows))
        self.assertEqual(idea_chat.latest_text(context, model='测试模型UXB2API', gateway=gateway), '回一句')


if __name__ == '__main__':
    unittest.main()
