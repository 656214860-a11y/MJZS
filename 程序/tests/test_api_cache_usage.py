"""API 缓存用量口径与 Claude 固定前缀断点（R2119）。

- OpenAI 兼容接口把命中写在 usage.prompt_tokens_details.cached_tokens，Responses 写在
  usage.input_tokens_details.cached_tokens；两处都要计入 cached_tokens。
- Claude 的 input_tokens 不含缓存读写，总输入 = input + cache_read + cache_creation，
  否则命中率会超过 100%、成本也算错；cache_creation_tokens 要一路保留到诊断。
- 流式请求要带 stream_options.include_usage，并读最后那个只有 usage 的分片。
- Claude 的 system 拆成固定块＋变化块，固定块上显式打 cache_control。
"""
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json
import urllib.request
import requests
from urllib3.response import HTTPResponse

from infra import model_diagnostics
import infra.model_pool as model_pool
import infra.model_router as model_router
import infra.pet_llm as pet_llm
import token_saver


CLAUDE_USAGE = {'input_tokens': 10, 'output_tokens': 2,
                'cache_read_input_tokens': 80, 'cache_creation_input_tokens': 30}


class UsageParsingTests(unittest.TestCase):
    def test_openai_nested_cached_tokens_count_as_hits(self):
        usage = pet_llm.usage_of({'data': {'usage': {
            'prompt_tokens': 100, 'completion_tokens': 5,
            'prompt_tokens_details': {'cached_tokens': 64}}}})
        self.assertEqual(usage, {'prompt_tokens': 100, 'completion_tokens': 5, 'cached_tokens': 64})

    def test_responses_input_details_cached_tokens_count_as_hits(self):
        usage = pet_llm.usage_of({'data': {'usage': {
            'input_tokens': 50, 'output_tokens': 4,
            'input_tokens_details': {'cached_tokens': 32}}}})
        self.assertEqual(usage, {'prompt_tokens': 50, 'completion_tokens': 4, 'cached_tokens': 32})

    def test_claude_total_input_includes_cache_reads_and_writes(self):
        usage = pet_llm.usage_of({'data': {'usage': dict(CLAUDE_USAGE)}})
        self.assertEqual(usage, {'prompt_tokens': 120, 'completion_tokens': 2, 'cached_tokens': 80,
                                 'cache_creation_tokens': 30})
        self.assertEqual(token_saver.anthropic_usage({'usage': dict(CLAUDE_USAGE)}),
                         {'prompt_tokens': 120, 'completion_tokens': 2, 'cached_tokens': 80,
                          'cache_creation_tokens': 30})

    def test_claude_hit_rate_never_exceeds_one(self):
        ledger = pet_llm.Ledger()
        ledger.record('claude', pet_llm.usage_of({'data': {'usage': dict(CLAUDE_USAGE)}}))
        self.assertEqual(ledger.hit_rate(), round(80 / 120, 3))
        self.assertEqual(ledger.entries[0]['cache_creation_tokens'], 30)

    def test_reported_usage_keeps_unreported_fields_absent(self):
        self.assertEqual(pet_llm.reported_usage({'prompt_tokens': 7}), {'prompt_tokens': 7})
        self.assertEqual(pet_llm.reported_usage({'prompt_tokens': 7, 'prompt_tokens_details': {'cached_tokens': 3}}),
                         {'prompt_tokens': 7, 'cached_tokens': 3})
        self.assertEqual(pet_llm.reported_usage(None), {})


class Fake:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, payload, headers, timeout):
        self.calls.append({'url': url, 'payload': payload})
        return self.responses.pop(0)


class ClaudeAdapterUsageTests(unittest.TestCase):
    def adapter(self):
        item = model_router.ModelAdapter(transport=Fake([]), key='sk-test')
        item.base_url, item.wire_api = 'https://x.test', 'messages'
        item.models = {'m': {'capabilities': (), 'cost': 1}}
        return item

    def test_messages_chat_keeps_cache_creation_and_total_input(self):
        item = self.adapter()
        item.transport = Fake([{'ok': True, 'status': 200, 'data': {
            'content': [{'type': 'text', 'text': '好'}], 'usage': dict(CLAUDE_USAGE)}}])
        result = item.chat([{'role': 'user', 'content': '做'}], model='m', system='人设')
        self.assertEqual(result['usage'], {'prompt_tokens': 120, 'completion_tokens': 2, 'cached_tokens': 80,
                                           'cache_creation_tokens': 30})

    def test_diagnostics_keep_cache_creation_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            path = model_diagnostics.record(Path(td), {
                'ok': True, 'model': 'm', 'text': '', 'usage': {
                    'prompt_tokens': 120, 'completion_tokens': 2, 'cached_tokens': 80,
                    'cache_creation_tokens': 30}})
            saved = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(saved['usage']['cache_creation_tokens'], 30)

    def test_writing_request_usage_reads_nested_hits(self):
        import writing_api
        from unittest.mock import Mock
        raw = Mock()
        raw.chat.return_value = {'ok': True, 'text': '正文', 'usage': {
            'prompt_tokens': 100, 'completion_tokens': 20, 'cached_tokens': 60},
            'data': {'usage': {'prompt_tokens': 100, 'completion_tokens': 20,
                               'prompt_tokens_details': {'cached_tokens': 60}}}}
        adapter = writing_api.WritingRequestAdapter(raw, {'context_length': 128000}, 'large')
        result = adapter.chat([{'role': 'user', 'content': '测试'}], options={'max_tokens': 4096})
        self.assertEqual(result['request_usage']['cached_tokens'], 60)


class StreamUsageTests(unittest.TestCase):
    def stream(self, body):
        seen, responses = [], []

        def respond(adapter, prepared, **settings):
            self.assertEqual(prepared.url, 'https://provider.invalid/v1/chat/completions')
            seen.append(prepared)
            response = requests.Response()
            response.status_code, response.url, response.reason = 200, prepared.url, 'OK'
            response.request = prepared
            response.raw = HTTPResponse(io.BytesIO(body), preload_content=False)
            responses.append(response)
            return response

        with patch('socket.getaddrinfo', side_effect=AssertionError('unexpected real DNS')), \
                patch('socket.socket.connect', side_effect=AssertionError('unexpected real network')), \
                patch.object(requests.adapters.HTTPAdapter, 'send', respond):
            import socket
            with self.assertRaisesRegex(AssertionError, 'unexpected real DNS'):
                socket.getaddrinfo('provider.invalid', 443)
            with socket.socket() as connection:
                with self.assertRaisesRegex(AssertionError, 'unexpected real network'):
                    connection.connect(('127.0.0.1', 443))
            try:
                with patch.dict('os.environ', {'DRAMA_SUPPRESS_NETWORK': '0', 'NO_PROXY': '*'}):
                    chunks = []
                    result = model_pool.http_stream('https://provider.invalid/v1/chat/completions',
                                                    {'model': 'm', 'messages': []}, {}, 3, chunks.append)
            finally:
                for response in responses:
                    response.close()
        self.assertEqual(len(seen), 1)
        self.assertTrue(all(response.raw.closed for response in responses))
        return result, seen, chunks

    def test_stream_requests_usage_and_reads_the_final_usage_chunk(self):
        body = (b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                b'data: {"choices":[],"usage":{"prompt_tokens":40,"completion_tokens":2,'
                b'"prompt_tokens_details":{"cached_tokens":32}}}\n\n'
                b'data: [DONE]\n')
        result, seen, chunks = self.stream(body)
        sent = json.loads(seen[0].body.decode('utf-8'))
        self.assertEqual(sent['stream_options'], {'include_usage': True})
        self.assertTrue(result['ok'])
        self.assertEqual(chunks, ['ok'])
        self.assertEqual(result['data']['choices'][0]['message']['content'], 'ok')
        self.assertEqual(result['data']['choices'][0]['finish_reason'], 'stop')
        self.assertEqual(pet_llm.usage_of(result), {'prompt_tokens': 40, 'completion_tokens': 2, 'cached_tokens': 32})


class ClaudeSystemBlockTests(unittest.TestCase):
    def test_plain_system_stays_a_string(self):
        body = token_saver.anthropic_payload('m', '人设', [{'role': 'user', 'content': '做'}])
        self.assertEqual(body['system'], '人设')
        self.assertEqual(body['cache_control'], {'type': 'ephemeral'})

    def test_split_system_marks_the_fixed_block_only(self):
        system = token_saver.split_system('固定规则', '\n项目接续：第3集')
        self.assertEqual(system, '固定规则\n项目接续：第3集')
        self.assertEqual(system.fixed, '固定规则')
        body = token_saver.anthropic_payload('m', system, [{'role': 'user', 'content': '做'}], ttl='1h')
        self.assertEqual(body['system'], [
            {'type': 'text', 'text': '固定规则', 'cache_control': {'type': 'ephemeral', 'ttl': '1h'}},
            {'type': 'text', 'text': '\n项目接续：第3集'}])
        # 单轮单条消息时，变化的用户消息不再按 1.25 倍写进缓存。
        self.assertNotIn('cache_control', body)

    def test_split_system_keeps_the_tail_marker_for_tool_rounds(self):
        system = token_saver.split_system('固定规则', '')
        body = token_saver.anthropic_payload('m', system, [{'role': 'user', 'content': '做'}], keep_tail=True)
        self.assertEqual(body['system'], [
            {'type': 'text', 'text': '固定规则', 'cache_control': {'type': 'ephemeral'}}])
        self.assertEqual(body['cache_control'], {'type': 'ephemeral'})

    def test_split_system_reads_as_plain_text_for_other_wires(self):
        system = token_saver.split_system('固定', '变化')
        item = model_router.ModelAdapter(key='sk-test')
        item.wire_api = 'chat'
        body = item.payload('m', [{'role': 'user', 'content': '做'}], {}, system)
        self.assertEqual(body['messages'][0], {'role': 'system', 'content': '固定变化'})
        self.assertIs(type(body['messages'][0]['content']), str)

    def test_router_keeps_the_tail_marker_when_tools_are_attached(self):
        item = model_router.ModelAdapter(key='sk-test')
        item.wire_api = 'messages'
        system = token_saver.split_system('固定', '变化')
        single = item.payload('m', [{'role': 'user', 'content': '做'}], {}, system)
        tools = item.payload('m', [{'role': 'user', 'content': '做'}], {'tools': []}, system)
        self.assertNotIn('cache_control', single)
        self.assertEqual(tools['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(single['system'][0]['cache_control'], {'type': 'ephemeral'})

    def test_writing_reply_sends_skill_rules_as_the_cached_block(self):
        import stage_config
        import writing_api
        from test_writing_api import make_project
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            stage_config.put(project, 'script', model='claude-test')
            record = {'context_length': 200000, 'label': 'Claude Test', 'model': 'claude-test', 'provider': 'anthropic',
                      'wire_api': 'messages', 'base_url': 'https://api.anthropic.com',
                      'key_env': 'ANTHROPIC_API_KEY'}
            done = {'ok': True, 'text': '好', 'data': {'content': [{'type': 'text', 'text': '好'}]}}
            with patch('writing_api.model_pool.pool', return_value={'claude-test': record}), \
                    patch('writing_api.PoolAdapter.chat', return_value=done) as chat:
                writing_api.reply(project, '测试创意')
            system = chat.call_args_list[0].kwargs['system']
            fixed = getattr(system, 'fixed', '')
            self.assertTrue(fixed)
            self.assertTrue(str(system).startswith(fixed))
            self.assertIn('受控剧本文件工具', fixed)
            self.assertGreater(len(system), len(fixed))
            context = str(system)[len(fixed):]
            self.assertNotIn('受控剧本文件工具', context)


if __name__ == '__main__':
    unittest.main()
