# -*- coding: utf-8 -*-
"""CLI 引擎后台调用的流式日志与续跑参数（R2478 可靠性轮）。

覆盖两点，与 API 稳定层（R2470）对齐的 CLI 侧能力：
1. ``communicate_or_kill`` 在 stdout/stderr 为 PIPE 时逐行回调 ``on_output``，
   边跑边把内容交给调用方（日志实时可见的接口基础），且回调异常不打断主流程。
2. ``background_command`` 给 claude 加 ``--resume``（复用 Claude对话.json 的 session id），
   codex 加 ``--resume``（复用 codex_tasks 持久化的 thread id）。

先红后绿：这些测试在实现前应失败（参数不存在 / 行为缺位）。
"""
import subprocess
import threading
import time
import os
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock


class _LineReader:
    """模拟 Popen 的 stdout/stderr：一个可迭代的文本行流。"""

    def __init__(self, lines):
        self._lines = list(lines)

    def __iter__(self):
        return iter(self._lines)


class _FakeStdin:
    def write(self, data):
        pass

    def flush(self):
        pass

    def close(self):
        pass


class _StreamProcess:
    """模拟带 PIPE 的已启动子进程：stdout/stderr 各是一行流，communicate 喂 stdin 后返回。"""

    returncode = 0

    def __init__(self, out_lines=(), err_lines=()):
        self.stdout = _LineReader(out_lines)
        self.stderr = _LineReader(err_lines)
        self.stdin = _FakeStdin()
        self._communicated = []
        self.killed = False

    def communicate(self, data, timeout=None):
        self._communicated.append((data, timeout))
        return None, None

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        return None


class CommunicateStreamTests(unittest.TestCase):
    def test_on_output_receives_each_stdout_and_stderr_line(self):
        from contract.platform_tools import communicate_or_kill

        process = _StreamProcess(out_lines=['第一行\n', '第二行\n'], err_lines=['警告行\n'])
        seen = []
        with mock.patch('contract.platform_tools.terminate_process_tree'):
            code = communicate_or_kill(process, '提示词', 60, on_output=lambda line, stream: seen.append((stream, line)))
        self.assertEqual(code, 0)
        self.assertEqual(sorted(seen), sorted([('stdout', '第一行\n'), ('stdout', '第二行\n'), ('stderr', '警告行\n')]))

    def test_on_output_callback_error_does_not_break_run(self):
        from contract.platform_tools import communicate_or_kill

        process = _StreamProcess(out_lines=['a\n', 'b\n'])

        def exploding(line, stream):
            raise RuntimeError('回调自己挂了')

        with mock.patch('contract.platform_tools.terminate_process_tree'):
            code = communicate_or_kill(process, '提示词', 60, on_output=exploding)
        self.assertEqual(code, 0)

    def test_without_on_output_behaviour_is_unchanged(self):
        # 未提供回调时，仍走 process.communicate 的原路径（向后兼容，文件对象直写不受影响）。
        from contract.platform_tools import communicate_or_kill

        process = _StreamProcess(out_lines=['x\n'])
        with mock.patch('contract.platform_tools.terminate_process_tree'):
            communicate_or_kill(process, '提示词', 60)
        # 原路径把 stdin 喂给 process.communicate，且不逐行回调（没有 on_output 就不会碰 stdout 迭代）。
        self.assertEqual(len(process._communicated), 1)
        self.assertEqual(process._communicated[0][0], '提示词')

    def test_stream_wait_observes_execution_cancel_and_terminates_tree(self):
        from contract.platform_tools import (ExecutionControl, ExecutionStopped,
                                             communicate_or_kill, execution_scope)

        process = _StreamProcess()
        process.wait = mock.Mock(side_effect=subprocess.TimeoutExpired('engine', .05))
        control = ExecutionControl(10)
        timer = threading.Timer(.03, control.cancel)
        timer.start()
        started = time.monotonic()
        try:
            with mock.patch('contract.platform_tools.terminate_process_tree', return_value=True) as terminate, \
                 execution_scope(control), self.assertRaises(ExecutionStopped) as caught:
                communicate_or_kill(process, '提示词', 60, on_output=lambda *_: None)
        finally:
            timer.cancel()
        self.assertTrue(caught.exception.started)
        self.assertLess(time.monotonic() - started, .5)
        terminate.assert_called_once_with(process)

    def test_non_stream_wait_observes_deadline_and_terminates_tree(self):
        from contract.platform_tools import (ExecutionControl, ExecutionStopped,
                                             communicate_or_kill, execution_scope)

        process = _StreamProcess()
        process.communicate = mock.Mock(side_effect=subprocess.TimeoutExpired('engine', .02))
        with mock.patch('contract.platform_tools.terminate_process_tree', return_value=True) as terminate, \
             execution_scope(ExecutionControl(.03)), self.assertRaises(ExecutionStopped) as caught:
            communicate_or_kill(process, '提示词', 60)
        self.assertEqual(caught.exception.reason, 'deadline')
        self.assertTrue(caught.exception.started)
        terminate.assert_called_once_with(process)

    def test_cancel_reaps_real_parent_and_grandchild_within_three_seconds(self):
        if os.name != 'nt':
            return
        from contract.platform_tools import (ExecutionControl, ExecutionStopped,
                                             communicate_or_kill, execution_scope,
                                             launch_text_process)

        with tempfile.TemporaryDirectory() as td:
            child_pid = Path(td) / 'child.pid'
            child_code = 'import time; time.sleep(60)'
            parent_code = (
                'import pathlib,subprocess,sys,time; '
                f'p=subprocess.Popen([sys.executable,"-c",{child_code!r}]); '
                f'pathlib.Path({str(child_pid)!r}).write_text(str(p.pid)); time.sleep(60)')
            process = launch_text_process(
                [sys.executable, '-c', parent_code], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            deadline = time.monotonic() + 2
            while not child_pid.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(child_pid.exists())
            grandchild = int(child_pid.read_text())
            control = ExecutionControl(10)
            timer = threading.Timer(.03, control.cancel)
            timer.start()
            try:
                with execution_scope(control), self.assertRaises(ExecutionStopped) as caught:
                    communicate_or_kill(process, '', 60, on_output=lambda *_: None)
            finally:
                timer.cancel()
            self.assertTrue(caught.exception.process_tree_terminated)
            self.assertIsNotNone(process.poll())
            listing = subprocess.run(
                ['tasklist', '/FI', f'PID eq {grandchild}', '/NH'], capture_output=True,
                timeout=3).stdout.decode('mbcs', 'replace')
            self.assertNotIn(str(grandchild), listing)


class BackgroundCommandResumeTests(unittest.TestCase):
    def test_claude_background_command_appends_resume_session(self):
        import workflow_engines

        with mock.patch.object(workflow_engines, 'find_program', return_value='claude.exe'), \
             mock.patch.object(workflow_engines, 'gui_claude_program', return_value=False), \
             mock.patch('workflow_settings.skill_roots_for_config', return_value=[]):
            args = workflow_engines.background_command(
                {'engine': 'claude', 'resume_session': 'abc-123'}, 'proj', 'out', 'report.md')
        self.assertIn('--resume', args)
        self.assertIn('abc-123', args)

    def test_claude_without_session_gets_session_id_and_no_resume(self):
        import uuid
        import workflow_engines

        config = {'engine': 'claude'}
        with mock.patch.object(workflow_engines, 'find_program', return_value='claude.exe'), \
             mock.patch.object(workflow_engines, 'gui_claude_program', return_value=False), \
             mock.patch('workflow_settings.skill_roots_for_config', return_value=[]):
            args = workflow_engines.background_command(config, 'proj', 'out', 'report.md')
        # 后台调用主动指定 --session-id（uuid），跑完后持久化供失败重试用 --resume 续上下文。
        self.assertNotIn('--resume', args)
        self.assertIn('--session-id', args)
        session_id = args[args.index('--session-id') + 1]
        self.assertEqual(str(uuid.UUID(session_id)), session_id)
        # uuid 回写 config，供 run_background 持久化到后台引擎会话.json。
        self.assertEqual(config['session_id'], session_id)

    def test_claude_with_resume_uses_resume_not_session_id(self):
        import workflow_engines

        config = {'engine': 'claude', 'resume_session': 'abc-123'}
        with mock.patch.object(workflow_engines, 'find_program', return_value='claude.exe'), \
             mock.patch.object(workflow_engines, 'gui_claude_program', return_value=False), \
             mock.patch('workflow_settings.skill_roots_for_config', return_value=[]):
            args = workflow_engines.background_command(config, 'proj', 'out', 'report.md')
        self.assertIn('--resume', args)
        self.assertNotIn('--session-id', args)
        self.assertNotIn('session_id', config)

    def test_codex_background_command_appends_resume_thread(self):
        import workflow_engines

        with mock.patch.object(workflow_engines, 'find_program', return_value='codex.exe'), \
             mock.patch('workflow_settings.skill_roots_for_config', return_value=[]):
            args = workflow_engines.background_command(
                {'engine': 'codex', 'resume_session': 'thread-9'}, 'proj', 'out', 'report.md')
        # codex 的续跑是 exec 的子命令：exec resume <session_id>，不是 --resume flag。
        self.assertIn('resume', args)
        self.assertIn('thread-9', args)
        self.assertEqual(args[1:3], ['exec', 'resume'])

    def test_codex_without_session_has_no_resume_subcommand(self):
        import workflow_engines

        with mock.patch.object(workflow_engines, 'find_program', return_value='codex.exe'), \
             mock.patch('workflow_settings.skill_roots_for_config', return_value=[]):
            args = workflow_engines.background_command(
                {'engine': 'codex'}, 'proj', 'out', 'report.md')
        self.assertNotIn('resume', args)


class EndToEndWiringTests(unittest.TestCase):
    """R2485 端到端接入：run_background 透传 on_output，监视页显示 engine_log。"""

    def test_run_background_forwards_on_output_to_codex(self):
        import workflow_engines

        seen = []
        with mock.patch.object(workflow_engines, 'ensure_request_context', lambda p, s: p), \
             mock.patch.object(workflow_engines, 'reserve_stage_process_slot', return_value='slot'), \
             mock.patch.object(workflow_engines, 'release_process_slot') as release, \
             mock.patch.object(workflow_engines, 'background_command', return_value=['cmd']), \
             mock.patch.object(workflow_engines, '_run', return_value=0) as fake_run:
            workflow_engines.run_background(
                {'engine': 'codex', 'stage': '剧本'}, 'proj', 'out', 'report.md', 'log.txt', '任务',
                on_output=lambda line, stream: seen.append((stream, line)))
        release.assert_called_once_with('slot')
        # on_output 透传给 _run 的第六个位置参数（timeout 之后的 on_output）。
        self.assertIsNotNone(fake_run.call_args.kwargs.get('on_output'))

    def test_previs_monitor_renders_engine_log(self):
        from orchestrator.previs_monitor import render

        state = {'engine_log': ['stdout 第一行', '[err] 警告行'], 'busy': True, 'summary': '制作中'}
        html_out = render(state, 'proj')
        self.assertIn('<pre class="engine-log">', html_out)
        self.assertIn('stdout 第一行', html_out)
        self.assertIn('[err] 警告行', html_out)

    def test_previs_monitor_without_log_omits_block(self):
        from orchestrator.previs_monitor import render

        html_out = render({'busy': False}, 'proj')
        self.assertNotIn('<pre class="engine-log">', html_out)


class CodexSessionPersistenceTests(unittest.TestCase):
    """R2491：codex 后台调用跑完后持久化 session id，重试时 resume 续跑。"""

    def test_extract_codex_thread_id_from_thread_started(self):
        import workflow_engines

        line = '{"type":"thread.started","thread_id":"01a1dab9-a479-7362-9f7f-58b83a4282e6"}'
        self.assertEqual(workflow_engines.extract_codex_thread_id(line),
                         '01a1dab9-a479-7362-9f7f-58b83a4282e6')

    def test_extract_codex_thread_id_ignores_other_events(self):
        import workflow_engines

        self.assertIsNone(workflow_engines.extract_codex_thread_id('{"type":"turn.started"}'))
        self.assertIsNone(workflow_engines.extract_codex_thread_id('不是 JSON'))
        self.assertIsNone(workflow_engines.extract_codex_thread_id(''))

    def test_extract_codex_message_text_from_agent_message(self):
        import workflow_engines

        line = '{"type":"item.completed","item":{"id":"item_4","type":"agent_message","text":"ok"}}'
        self.assertEqual(workflow_engines.extract_codex_message_text(line), 'ok')

    def test_extract_codex_message_text_ignores_non_message_events(self):
        import workflow_engines

        self.assertIsNone(workflow_engines.extract_codex_message_text('{"type":"thread.started","thread_id":"x"}'))
        self.assertIsNone(workflow_engines.extract_codex_message_text('{"type":"turn.completed","usage":{}}'))
        self.assertIsNone(workflow_engines.extract_codex_message_text('{"type":"item.completed","item":{"type":"error","message":"x"}}'))

    def test_codex_background_command_adds_json_flag(self):
        import workflow_engines

        with mock.patch.object(workflow_engines, 'find_program', return_value='codex.exe'), \
             mock.patch('workflow_settings.skill_roots_for_config', return_value=[]):
            args = workflow_engines.background_command(
                {'engine': 'codex'}, 'proj', 'out', 'report.md')
        self.assertIn('--json', args)

    def test_save_and_load_background_session_roundtrip(self):
        import workflow_engines
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            workflow_engines.save_background_session(project, 'previs', 'codex', 'uuid-123')
            self.assertEqual(workflow_engines.load_background_session(project, 'previs', 'codex'), 'uuid-123')
            # 不同 engine 互不覆盖。
            workflow_engines.save_background_session(project, 'previs', 'claude', 'uuid-456')
            self.assertEqual(workflow_engines.load_background_session(project, 'previs', 'codex'), 'uuid-123')
            self.assertEqual(workflow_engines.load_background_session(project, 'previs', 'claude'), 'uuid-456')
            # 未记录时返回 None。
            self.assertIsNone(workflow_engines.load_background_session(project, 'previs', 'qwen'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
