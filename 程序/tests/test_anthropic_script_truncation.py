"""Anthropic 原生 Messages 的截断标记必须阻断剧本采用。"""
import tempfile
import unittest
from unittest.mock import Mock, patch

from agent.core import save_text
from model_router import ModelAdapter
import hollmwood_roles as roles
import writing_api


class NativeAdapter(ModelAdapter):
    wire_api = 'messages'
    base_url = 'https://example.invalid/v1'

    def __init__(self, answers):
        self.answers = iter(answers)
        self.requests = []
        super().__init__(transport=self.respond, key='test-key')

    def respond(self, url, payload, headers, timeout):
        self.requests.append((url, payload, headers))
        text, stop = next(self.answers)
        return {'ok': True, 'status': 200, 'data': {
            'content': [{'type': 'text', 'text': text}], 'stop_reason': stop}}


class AnthropicScriptTruncationTests(unittest.TestCase):
    def test_native_stop_reason_survives_adapter_without_changing_protocol(self):
        for stop in ('max_tokens', 'end_turn', 'tool_use'):
            with self.subTest(stop=stop):
                adapter = NativeAdapter([('正文', stop)])
                result = adapter.chat([{'role': 'user', 'content': '任务'}],
                                      {'max_tokens': 8192}, 'claude-test', '规则')
                self.assertEqual(result['response_meta']['finish_reason'], stop)
                url, payload, headers = adapter.requests[0]
                self.assertEqual(url, 'https://example.invalid/v1/messages')
                self.assertEqual(payload['system'], '规则')
                self.assertEqual(payload['messages'], [{'role': 'user', 'content': '任务'}])
                self.assertEqual(payload['max_tokens'], 8192)
                self.assertIn('x-api-key', headers)
                self.assertNotIn('Authorization', headers)

    def test_all_roles_reject_native_truncation_and_accept_complete_text(self):
        names = ('director', 'writer', 'editor', 'actor', 'writer_revision',
                 'editor_revision', 'actor_revision', 'director_review_writer',
                 'director_review_editor', 'director_review_actor')
        for role in names:
            with self.subTest(role=role), tempfile.TemporaryDirectory() as folder:
                adapter = NativeAdapter([('半截正文', 'max_tokens')])
                with self.assertRaisesRegex(roles.RoleExecutionError, '输出额度耗尽.*max_tokens'):
                    roles._ask(adapter, 'claude-test', role, '规则', '任务', folder, 1,
                               None, stream=lambda _: None, publish_log=save_text)
                self.assertEqual(len(adapter.requests), 1)
                complete = NativeAdapter([('完整正文', 'end_turn')])
                self.assertEqual(roles._ask(complete, 'claude-test', role, '规则', '任务',
                                           folder, 1, None, publish_log=save_text), '完整正文')
                self.assertEqual(len(complete.requests), 1)

    def test_native_plain_reply_rejects_partial_text_before_auto_save(self):
        for text in ('# 自然剧本\n' + '阿远：请把照片交给我。\n' * 80, ''):
            with self.subTest(empty=not text), tempfile.TemporaryDirectory() as folder:
                adapter = NativeAdapter([(text, 'max_tokens'), (text, 'max_tokens')])
                publish = Mock()
                result = writing_api._reply_with_project_tools(
                    adapter, 'claude-test', '规则', '任务', folder, publish=publish)
                self.assertFalse(result['ok'])
                self.assertIn('max_tokens', result['error'])
                self.assertEqual(result['text'], '')
                self.assertEqual(len(adapter.requests), 1)
                writing_api._auto_save_script_raw(folder, result, publish=publish)
                publish.assert_not_called()

    def test_four_role_api_never_publishes_truncated_actor_script(self):
        answers = [(text, 'end_turn') for text in
                   ('节奏计划', '编剧稿', 'APPROVED', '编辑稿', 'APPROVED')]
        answers += [('半截演员稿', 'max_tokens'), ('APPROVED', 'end_turn')]
        adapter = NativeAdapter(answers)
        publish = Mock()
        with tempfile.TemporaryDirectory() as folder, \
             patch('writing_api.PoolAdapter', return_value=adapter), \
             patch('workflow_settings.skill_prompt', return_value='规则'), \
             patch('writing_api.hollmwood_gateway', return_value={'publish_log': save_text}):
            result = writing_api._hollmwood_reply(
                folder, 'claude-test', {},
                {'hollmwood': {'enabled': True, 'rhythm': {}, 'roles': {}}},
                {'story_summary': '雨夜寻人'}, publish=publish)
        self.assertFalse(result['ok'])
        self.assertIn('max_tokens', result['error'])
        self.assertEqual(len(adapter.requests), 6)
        publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
