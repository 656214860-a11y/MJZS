import tempfile
import unittest
import uuid
import hashlib
import json
import subprocess
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

import workflow_engines
from orchestrator import workflow_tasks
from agent.core import save, read


class ClaudeWritingSessionTests(unittest.TestCase):
    def test_restart_intent_only_reads_user_command(self):
        for text in ('重新创作', '重新输出项目设定', '请重新生成角色卡。', '重新创作项目大纲\n\n附档内容'):
            with self.subTest(text=text):
                self.assertTrue(workflow_tasks.writing_restart_requested(text))
        for text in ('确认', '继续输出项目大纲', '不要重新创作', '修改主角', '确认\n\n重新输出项目设定', '角色说：重新创作'):
            with self.subTest(text=text):
                self.assertFalse(workflow_tasks.writing_restart_requested(text))

    def test_new_session_does_not_resume_persisted_session(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            binding = project / '工作流任务/Claude对话.json'
            previous = str(uuid.uuid4())
            save(binding, {'writing': previous, 'storyboard': 'keep'})
            process = Mock()
            with patch.object(workflow_engines, 'find_program', return_value='claude.exe'), \
                    patch.object(Path, 'glob', return_value=iter([Path('old.jsonl')])), \
                    patch.object(workflow_engines, 'launch_windows_app', return_value=process) as launch, \
                    patch.object(workflow_engines, 'reserve_stage_process_slot', return_value=object()), \
                    patch.object(workflow_engines, 'register_process'):
                result = workflow_engines.launch_interactive(project, 'writing', '测试', '完整任务',
                    {'engine': 'claude'}, followup='续接任务', new_session=True)
            args = launch.call_args.kwargs['args']
            self.assertIn('--session-id', args)
            self.assertNotIn('--resume', args)
            self.assertNotEqual(read(binding)['writing'], previous)
            self.assertEqual(read(binding)['storyboard'], 'keep')
            self.assertEqual(Path(result['task_file']).read_text(encoding='utf-8'), '完整任务')

    def test_restart_waits_for_idle_cli_exit_before_releasing_slot(self):
        process = Mock(pid=123)
        process.poll.return_value = None
        with patch('console_submit.send', return_value={'ok': True}) as send, \
                patch.object(workflow_engines, 'forget_process') as forget:
            workflow_engines.close_for_restart(Path('project'), process)
        send.assert_called_once_with(123, '/exit')
        process.wait.assert_called_once_with(timeout=10)
        forget.assert_called_once_with(Path('project'), process)
        process.terminate.assert_not_called()

    def test_busy_cli_is_not_killed_or_forgotten(self):
        process = Mock(pid=123)
        process.poll.return_value = None
        with patch('console_submit.send', return_value={'ok': False, 'reason': '输入框忙碌'}), \
                patch.object(workflow_engines, 'forget_process') as forget:
            with self.assertRaisesRegex(ValueError, '输入框忙碌'):
                workflow_engines.close_for_restart(Path('project'), process)
        process.wait.assert_not_called()
        process.terminate.assert_not_called()
        forget.assert_not_called()

    def test_exit_timeout_keeps_old_process_registered(self):
        process = Mock(pid=123)
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired('claude', 10)
        with patch('console_submit.send', return_value={'ok': True}), \
                patch.object(workflow_engines, 'forget_process') as forget:
            with self.assertRaisesRegex(ValueError, '尚未退出'):
                workflow_engines.close_for_restart(Path('project'), process)
        forget.assert_not_called()

    def test_normal_continuation_resumes_persisted_session(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            previous = str(uuid.uuid4())
            save(project / '工作流任务/Claude对话.json', {'writing': previous})
            with patch.object(workflow_engines, 'find_program', return_value='claude.exe'), \
                    patch.object(Path, 'glob', return_value=iter([Path('old.jsonl')])), \
                    patch.object(workflow_engines, 'launch_windows_app', return_value=Mock()) as launch, \
                    patch.object(workflow_engines, 'reserve_stage_process_slot', return_value=object()), \
                    patch.object(workflow_engines, 'register_process'):
                result = workflow_engines.launch_interactive(project, 'writing', '测试', '初始',
                    {'engine': 'claude'}, followup='继续阶段')
            self.assertEqual(launch.call_args.kwargs['args'][1:3], ['--resume', previous])
            self.assertEqual(Path(result['task_file']).read_text(encoding='utf-8'), '继续阶段')

    def test_desktop_restart_closes_old_before_requesting_new_slot(self):
        from desktop import Desktop
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            config = {'engine': 'claude', 'program': 'claude', 'model': ''}
            key = (str(project), 'writing', 'claude', hashlib.sha256(
                json.dumps(config, sort_keys=True).encode()).hexdigest())
            old = Mock(); old.poll.return_value = None
            new = Mock()
            desktop = SimpleNamespace(root=project, worker=False, status=Mock(), notifier=Mock(),
                projects=SimpleNamespace(info={'projects': []}), flow_processes={key: old},
                async_=lambda fn, done: done(fn()), update_script_interrupt_button=Mock())
            events = []
            with patch('workflow_settings.freeze_skills', side_effect=lambda c: c), \
                    patch('orchestrator.agent_skill_sync.sync_agent_skills',
                          return_value={'errors': [], 'conflicts': []}), \
                    patch('agent_dispatch.claim', return_value={'duplicate': False}), \
                    patch('agent_dispatch.finish'), \
                    patch('workflow_context.snapshot', return_value={'scripts': [], 'storyboards': [], 'assets': [], 'read_errors': []}) as snapshot, \
                    patch('orchestrator.workflow_context_controller.request_stage_instruction', return_value=('', 'script_full_index')) as instruction, \
                    patch('workflow_engines.prompt_with_settings', side_effect=lambda text, *a, **kw: text), \
                    patch('workflow_engines.close_for_restart', side_effect=lambda *a: events.append('close')) as close, \
                    patch('workflow_engines.request_stage_process_slot', side_effect=lambda *a: (events.append('slot') or {'state': 'granted', 'slot': 'slot'})), \
                    patch('workflow_engines.submit_existing') as submit, \
                    patch('workflow_engines.launch_interactive', return_value={'process': new, 'engine': 'Claude', 'task_file': 'task.md'}) as launch:
                Desktop.open_flow_agent(desktop, 'writing', '剧本准备', '重新创作', '旧续接', _config=config, new_session=True)
            self.assertEqual(events, ['close', 'slot'])
            close.assert_called_once_with(project, old)
            self.assertTrue(launch.call_args.kwargs['new_session'])
            self.assertIs(desktop.flow_processes[key], new)
            submit.assert_not_called()
            snapshot.assert_not_called()
            instruction.assert_not_called()

    def test_bounded_first_stage_has_no_implicit_brief_read(self):
        with tempfile.TemporaryDirectory() as td, \
                patch('orchestrator.workflow_tasks._agent_delivery_contract', return_value='保存约定'):
            prompt = workflow_tasks.script_prompt(td, None, 'writing', creative_text='重新输出项目设定',
                agent_delivery=True, bounded_input=True)
            self.assertNotIn('brief_complete.json', prompt)
            self.assertIn('阶段①无需扫描已有文件', prompt)

    def test_desktop_forwards_explicit_restart_only(self):
        from desktop import Desktop
        desktop = SimpleNamespace(root=Path('project'), open_flow_agent=Mock())
        with patch('orchestrator.workflow_tasks._agent_delivery_contract', return_value='保存约定'):
            for text, expected in (('重新输出项目设定', True), ('确认', False)):
                Desktop.start_script_workflow(desktop, text, config={'display_model': 'Claude Code'})
                self.assertEqual(desktop.open_flow_agent.call_args.kwargs['new_session'], expected)

    def test_separate_confirmations_do_not_share_dispatch_signature(self):
        from desktop import Desktop
        from agent_dispatch import signature
        desktop = SimpleNamespace(root=Path('project'), open_flow_agent=Mock())
        config = {'display_model': 'Claude Code', 'engine': 'claude'}
        keys = []
        with patch('orchestrator.workflow_tasks._agent_delivery_contract', return_value='保存约定'), \
                patch('desktop.time.time', return_value=100.0) as clock:
            for timestamp in (100.0, 101.0):
                clock.return_value = timestamp
                Desktop.start_script_workflow(desktop, '确认', config=config)
                _, _, prompt, followup = desktop.open_flow_agent.call_args.args
                keys.append(signature('writing', prompt, followup, config, {}))
        self.assertNotEqual(*keys)

    def test_agent_tasks_limit_history_reads_but_api_prompt_unchanged(self):
        with tempfile.TemporaryDirectory() as td, \
                patch('orchestrator.workflow_tasks._agent_delivery_contract', return_value='保存约定'):
            for prompt in (workflow_tasks.script_prompt(td, None, 'writing', creative_text='重新输出角色卡', agent_delivery=True),
                           workflow_tasks.script_followup(None, 'writing', project=td, creative_text='确认', agent_delivery=True)):
                self.assertIn('不要遍历或批量读取', prompt)
                self.assertIn('对话.json', prompt)
                self.assertIn('responses', prompt)
            api = workflow_tasks.script_prompt(td, None, 'writing', creative_text='确认')
            self.assertNotIn('不要遍历或批量读取', api)
