"""受控 Claude CLI 写作适配器的离线回归；Claude 桌面程序不再是直接 API 对话模型。"""
import json
import tempfile
import unittest
from unittest.mock import Mock, patch

import model_pool
import stage_config
import workflow_engines
import writing_api
from agent.core import save
import test_writing_api as fixtures
import project_stages


class ClaudeWritingRolesTests(unittest.TestCase):
    def setup_project(self, td):
        project = fixtures.make_project(td)
        stage_config.put(project, 'script', model='claude-desktop', skills=[])
        save(project_stages.writing(project) / 'brief_complete.json', fixtures.WritingApiTests.complete_brief())
        return project

    def test_claude_desktop_model_stays_on_the_interactive_agent_channel(self):
        with tempfile.TemporaryDirectory() as td, patch('model_pool.pool', return_value=model_pool.default_pool()):
            project = self.setup_project(td)
            self.assertEqual(writing_api.selected_model(project), ('', {}))
            request = writing_api.capture_request(project)
            self.assertEqual(request['id'], '')

    def test_cancelled_cli_never_starts_a_process(self):
        with patch('workflow_engines.subprocess.Popen') as spawn:
            result = workflow_engines.ClaudeWritingAdapter('.', {}, cancelled=lambda: True).chat([])
        self.assertFalse(result['ok'])
        spawn.assert_not_called()

    def test_running_cli_cancellation_terminates_registered_process(self):
        import subprocess
        process = Mock(returncode=0)
        process.poll.return_value = 0
        process.communicate.side_effect = [subprocess.TimeoutExpired('claude', .25), ('', '')]
        cancelled = Mock(side_effect=[False, False, True])
        with tempfile.TemporaryDirectory() as td, patch('workflow_engines.find_program', return_value='claude.exe'), \
                patch('workflow_engines.subprocess.Popen', return_value=process), \
                patch('workflow_engines.terminate_process_tree') as terminate, \
                patch('workflow_engines.forget_process') as forget:
            result = workflow_engines.ClaudeWritingAdapter(td, {}, cancelled=cancelled).chat([])
        self.assertFalse(result['ok'])
        terminate.assert_called_once_with(process)
        forget.assert_called_once()

    def test_cli_error_keeps_returned_body(self):
        process = Mock(returncode=1)
        process.communicate.return_value = (json.dumps({'result': '尚未完成的正文', 'is_error': True}), '')
        with patch('workflow_engines.find_program', return_value='claude.exe'), \
                patch('workflow_engines.subprocess.Popen', return_value=process):
            result = workflow_engines.ClaudeWritingAdapter('.', {}).chat([])
        self.assertFalse(result['ok'])
        self.assertEqual(result['text'], '尚未完成的正文')

    def test_print_process_is_isolated_and_returns_usage(self):
        process = Mock(returncode=0)
        process.communicate.return_value = (json.dumps({'result': '完整正文', 'is_error': False,
            'usage': {'input_tokens': 20, 'output_tokens': 12, 'cache_read_input_tokens': 8}}), '')
        with tempfile.TemporaryDirectory() as td, patch('workflow_engines.find_program', return_value='claude.exe'), \
                patch('workflow_engines.subprocess.Popen', return_value=process) as spawn, \
                patch('workflow_engines.register_process') as register, \
                patch('workflow_engines.forget_process') as forget:
            adapter = workflow_engines.ClaudeWritingAdapter(td, {'engine': 'claude', 'model': 'opus', 'program': ''})
            result = adapter.chat([{'role': 'user', 'content': '创作资料'}], system='导演规则', options={'max_tokens': 4096})
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], '完整正文')
        self.assertEqual(result['usage']['cached_tokens'], 8)
        args = spawn.call_args.args[0]
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertIn('--no-session-persistence', args)
        self.assertNotIn('--resume', args)
        self.assertNotEqual(Path(spawn.call_args.kwargs['cwd']), Path(td))
        self.assertIn('导演规则', process.communicate.call_args.args[0])
        register.assert_called_once()
        forget.assert_called_once()

    def test_invalid_cli_json_is_failure_without_retry(self):
        process = Mock(returncode=0)
        process.communicate.return_value = ('not json', '')
        with tempfile.TemporaryDirectory() as td, patch('workflow_engines.find_program', return_value='claude.exe'), \
                patch('workflow_engines.subprocess.Popen', return_value=process) as spawn:
            result = workflow_engines.ClaudeWritingAdapter(td, {'engine': 'claude'}).chat([])
        self.assertFalse(result['ok'])
        self.assertEqual(spawn.call_count, 1)


if __name__ == '__main__':
    unittest.main()
