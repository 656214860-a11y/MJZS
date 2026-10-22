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
            'workflow_context_controller.request_stage_instruction': Mock(return_value=('', 'stage')),
            'workflow_context_budget.prepare_request_context': lambda text, *a, **k: (text, {}),
            'workflow_engines.prompt_with_settings': lambda prompt, config, stage: prompt,
            'prompt_window.copy_text': Mock(),
            'codex_paste.paste_existing': self.paste,
            'platform_tools.launch_windows_app': Mock(),
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
        with self.stubs(), patch('qwen_adapter.window_title', return_value='Qwen·样片') as title:
            self.open(host, 'storyboard', {'engine': 'qwen', 'program': '', 'model': ''})
        title.assert_called_once_with('样片', 'storyboard', 3)
        self.assertEqual('Qwen·样片', host.async_.call_args.args[0].__self__.title)

    def test_codex_skill_sync_problems_stop_before_claiming(self):
        host = self.host()
        sync = {'errors': ['缺技能'], 'conflicts': ['重名']}
        with self.stubs(), patch('codex_skill_sync.sync_codex_skills', return_value=sync), \
                self.assertRaisesRegex(ValueError, '^Codex 技能同步未完成：缺技能; 重名$'):
            self.open(host, 'storyboard', {'engine': 'codex', 'program': '', 'model': ''})
        self.finish.assert_not_called()

    def test_previs_opens_blender_then_pastes_into_gpt_desktop(self):
        host = self.host()
        config = {'engine': 'codex', 'program': '', 'model': '', 'desktop_program': 'Codex.exe'}
        task = {'url': 'codex://new', 'title': '样片 任务', 'mode': 'new', 'prompt': '全文'}
        with self.stubs(), patch('codex_skill_sync.sync_codex_skills', return_value={'errors': [], 'conflicts': []}), \
                patch('native_apps.open_blender') as blender, \
                patch('codex_tasks.prepare_task', return_value=task) as prepare, \
                patch('desktop_idea_chat.open_target') as target, \
                patch('platform_tools.launch_windows_app') as launch:
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
        with self.stubs(), patch('qwen_adapter.window_title', return_value='Q'), \
                patch('qwen_adapter.submit_existing', return_value='已续发') as submit:
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


if __name__ == '__main__':
    unittest.main()
