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
        from platform_tools import communicate_or_kill

        process = _StreamProcess(out_lines=['第一行\n', '第二行\n'], err_lines=['警告行\n'])
        seen = []
        with mock.patch('platform_tools.terminate_process_tree'):
            code = communicate_or_kill(process, '提示词', 60, on_output=lambda line, stream: seen.append((stream, line)))
        self.assertEqual(code, 0)
        self.assertEqual(sorted(seen), sorted([('stdout', '第一行\n'), ('stdout', '第二行\n'), ('stderr', '警告行\n')]))

    def test_on_output_callback_error_does_not_break_run(self):
        from platform_tools import communicate_or_kill

        process = _StreamProcess(out_lines=['a\n', 'b\n'])

        def exploding(line, stream):
            raise RuntimeError('回调自己挂了')

        with mock.patch('platform_tools.terminate_process_tree'):
            code = communicate_or_kill(process, '提示词', 60, on_output=exploding)
        self.assertEqual(code, 0)

    def test_without_on_output_behaviour_is_unchanged(self):
        # 未提供回调时，仍走 process.communicate 的原路径（向后兼容，文件对象直写不受影响）。
        from platform_tools import communicate_or_kill

        process = _StreamProcess(out_lines=['x\n'])
        with mock.patch('platform_tools.terminate_process_tree'):
            communicate_or_kill(process, '提示词', 60)
        # 原路径把 stdin 喂给 process.communicate，且不逐行回调（没有 on_output 就不会碰 stdout 迭代）。
        self.assertEqual(len(process._communicated), 1)
        self.assertEqual(process._communicated[0][0], '提示词')


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

    def test_claude_without_session_has_no_resume(self):
        import workflow_engines

        with mock.patch.object(workflow_engines, 'find_program', return_value='claude.exe'), \
             mock.patch.object(workflow_engines, 'gui_claude_program', return_value=False), \
             mock.patch('workflow_settings.skill_roots_for_config', return_value=[]):
            args = workflow_engines.background_command(
                {'engine': 'claude'}, 'proj', 'out', 'report.md')
        self.assertNotIn('--resume', args)

    def test_codex_background_command_appends_resume_thread(self):
        import workflow_engines

        with mock.patch.object(workflow_engines, 'find_program', return_value='codex.exe'), \
             mock.patch('workflow_settings.skill_roots_for_config', return_value=[]):
            args = workflow_engines.background_command(
                {'engine': 'codex', 'resume_session': 'thread-9'}, 'proj', 'out', 'report.md')
        self.assertIn('--resume', args)
        self.assertIn('thread-9', args)


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
        from previs_monitor import render

        state = {'engine_log': ['stdout 第一行', '[err] 警告行'], 'busy': True, 'summary': '制作中'}
        html_out = render(state, 'proj')
        self.assertIn('<pre class="engine-log">', html_out)
        self.assertIn('stdout 第一行', html_out)
        self.assertIn('[err] 警告行', html_out)

    def test_previs_monitor_without_log_omits_block(self):
        from previs_monitor import render

        html_out = render({'busy': False}, 'proj')
        self.assertNotIn('<pre class="engine-log">', html_out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
