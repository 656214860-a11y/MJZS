"""受控 Claude CLI 与真实 HOLLMWOOD 执行器的离线回归。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import model_pool
import stage_config
import workflow_engines
import writing_api
from agent.core import save
from stage_execution_service import publish_stage_text
import test_writing_api as fixtures
import project_stages


class ClaudeWritingRolesTests(unittest.TestCase):
    def setup_project(self, td):
        project = fixtures.make_project(td)
        stage_config.put(project, 'script', model='claude-desktop', skills=[], hollmwood_enabled=True)
        save(project_stages.writing(project) / 'brief_complete.json', fixtures.WritingApiTests.complete_brief())
        return project

    def test_cli_enabled_is_managed_and_off_remains_interactive(self):
        with tempfile.TemporaryDirectory() as td, patch('model_pool.pool', return_value=model_pool.default_pool()):
            project = self.setup_project(td)
            request = writing_api.capture_request(project)
            self.assertEqual(request['id'], 'claude-desktop')
            self.assertEqual(request['settings']['engine'], 'claude')
            self.assertNotEqual(request['settings']['model'], 'claude-desktop')
            stage_config.put(project, 'script', hollmwood_enabled=False)
            self.assertEqual(writing_api.selected_model(project), ('', {}))

    def test_cli_runs_four_roles_and_three_reviews_without_http(self):
        with tempfile.TemporaryDirectory() as td, patch('model_pool.pool', return_value=model_pool.default_pool()):
            project = self.setup_project(td)
            fixtures.WritingApiTests.confirmed_preparation(project)
            script = fixtures.WritingApiTests.natural_script(20)
            replies = ['导演计划', script, 'APPROVED', script, 'APPROVED', script, 'APPROVED']
            with patch.object(workflow_engines.ClaudeWritingAdapter, 'chat', side_effect=[
                    {'ok': True, 'text': text} for text in replies]) as chat, \
                    patch('writing_api.PoolAdapter') as http:
                result = writing_api.reply(project, '生成第1集', publish=publish_stage_text)
            self.assertTrue(result['ok'], result)
            self.assertEqual(chat.call_count, 7)
            http.assert_not_called()
            for call, role in zip(chat.call_args_list, ('导演', '编剧', '导演审核人', '剧本编辑', '导演审核人', '演员与表演指导', '导演审核人')):
                self.assertIn('你是漫剧' + role, call.kwargs['system'])
            self.assertTrue(list(project_stages.writing(project).rglob('*自然剧本*.md')))

    def test_cli_rejected_writer_stops_before_editor_and_publication(self):
        with tempfile.TemporaryDirectory() as td, patch('model_pool.pool', return_value=model_pool.default_pool()):
            project = self.setup_project(td)
            fixtures.WritingApiTests.confirmed_preparation(project)
            script = fixtures.WritingApiTests.natural_script(20)
            replies = ['计划', script, 'REVISE: 修改结尾', script, 'REVISE: 仍未修改']
            with patch.object(workflow_engines.ClaudeWritingAdapter, 'chat', side_effect=[
                    {'ok': True, 'text': text} for text in replies]) as chat:
                result = writing_api.reply(project, '生成', publish=publish_stage_text)
            self.assertFalse(result['ok'])
            self.assertEqual(result['hollmwood_review_failed_role'], 'writer')
            self.assertEqual(chat.call_count, 5)
            self.assertFalse((project_stages.writing(project) / 'script_raw.md').exists())

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

    def test_cli_preparation_does_not_skip_to_roles(self):
        with tempfile.TemporaryDirectory() as td, patch('model_pool.pool', return_value=model_pool.default_pool()):
            project = self.setup_project(td)
            with patch.object(workflow_engines.ClaudeWritingAdapter, 'chat', return_value={
                    'ok': True, 'text': '# 项目设定\n雨夜照相馆的少年追查底片。\n待确认'}) as chat, \
                    patch('writing_api._hollmwood_reply') as roles:
                result = writing_api.reply(project, '开始', publish=publish_stage_text)
            self.assertTrue(result['ok'], result)
            self.assertEqual(chat.call_count, 1)
            roles.assert_not_called()

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
