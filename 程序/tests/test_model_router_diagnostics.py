# -*- coding: utf-8 -*-
"""模型响应诊断必须只暴露协议元数据，不丢失空正文定位信息。"""
import unittest

from model_router import ModelAdapter


class _Adapter(ModelAdapter):
    provider = 'Test'
    key_env = 'TEST_KEY'
    base_url = 'https://example.invalid/v1'
    models = {'test-model': {}}

    def headers(self):
        return {}


class ModelRouterDiagnosticsTests(unittest.TestCase):
    def test_sse_length_survives_transport_and_adapter(self):
        import io
        from unittest.mock import patch
        response = io.BytesIO(
            b'data: {"choices":[{"delta":{"content":"partial"}}]}\n'
            b'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n'
            b'data: [DONE]\n')
        with patch('model_pool._http_opener') as opener:
            opener.return_value.open.return_value = response
            result = _Adapter(key='sk-test').stream([], model='test-model', on_chunk=lambda _: None)
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], 'partial')
        self.assertEqual(result['response_meta']['finish_reason'], 'length')

    def responses_adapter(self, transport):
        item = _Adapter(transport=transport, key='sk-test')
        item.wire_api = 'responses'
        return item

    def test_responses_payload_and_text_follow_the_native_protocol(self):
        calls=[]
        def transport(url, payload, _headers, _timeout):
            calls.append((url, payload))
            return {'ok': True, 'status': 200, 'error': '', 'data': {
                'id': 'resp_123', 'status': 'completed',
                'output': [{'type': 'message', 'content': [
                    {'type': 'output_text', 'text': '第一段'},
                    {'type': 'output_text', 'text': '第二段'}]}],
                'usage': {'input_tokens': 12, 'output_tokens': 7}}}
        result=self.responses_adapter(transport).chat(
            [{'role': 'user', 'content': 'private prompt'}], {'max_tokens': 321}, 'test-model', '系统')
        self.assertTrue(result['ok'])
        self.assertEqual(calls[0][0], 'https://example.invalid/v1/responses')
        self.assertEqual(calls[0][1]['max_output_tokens'], 321)
        self.assertNotIn('max_tokens', calls[0][1])
        self.assertEqual(calls[0][1]['input'][0], {'role': 'system', 'content': '系统'})
        self.assertEqual(result['text'], '第一段第二段')
        self.assertEqual(result['usage'], {'prompt_tokens': 12, 'completion_tokens': 7, 'cached_tokens': 0})

    def test_responses_ignores_tool_outputs_and_keeps_empty_text_empty(self):
        def transport(*_args):
            return {'ok': True, 'status': 200, 'error': '', 'data': {
                'output': [{'type': 'function_call', 'name': 'unsafe_tool', 'arguments': 'secret'},
                           {'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'no'}]}]}}
        result=self.responses_adapter(transport).chat([], model='test-model')
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], '')
        self.assertEqual(result['response_meta']['content_length'], 0)

    def test_responses_error_preserves_status_without_fabricating_text(self):
        def transport(*_args):
            return {'ok': False, 'status': 400, 'error': 'HTTP 400 invalid input', 'data': {
                'error': {'message': 'invalid input'}, 'usage': {'input_tokens': 3, 'output_tokens': 0}}}
        result=self.responses_adapter(transport).chat([], model='test-model')
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 400)
        self.assertEqual(result['text'], '')
        self.assertEqual(result['usage'], {'prompt_tokens': 3, 'completion_tokens': 0, 'cached_tokens': 0})
        self.assertEqual(result['error_class'], 'protocol')

    def test_error_classes_keep_configuration_and_protocol_distinct(self):
        from model_router import error_class
        self.assertEqual(error_class('ValueError：DeepSeek 缺少 API Key'), 'authentication')
        self.assertEqual(error_class('HTTP 404 /chat/completions'), 'protocol')
        self.assertEqual(error_class('连接超时'), 'timeout')

    def test_openai_compatible_empty_content_keeps_safe_diagnostics(self):
        def transport(_url, _payload, _headers, _timeout):
            return {'ok': True, 'status': 200, 'error': '', 'data': {
                'id': 'req_safe_123', 'choices': [{'finish_reason': 'length', 'message': {
                    'reasoning_content': 'private reasoning', 'content': ''}}]}}
        result = _Adapter(transport=transport).chat(
            [{'role': 'user', 'content': 'private prompt'}], model='test-model')
        self.assertTrue(result['ok'])
        self.assertEqual(result['text'], '')
        self.assertEqual(result['response_meta'], {
            'requested_model': 'test-model', 'wire_api': 'chat', 'response_id': 'req_safe_123',
            'finish_reason': 'length', 'response_shape': ['choices', 'id'],
            'message_fields': ['content', 'reasoning_content'],
            'reasoning_fields': ['reasoning_content'], 'reasoning_lengths': {'reasoning_content': 17},
            'content_length': 0})
        self.assertNotIn('private prompt', str(result['response_meta']))
        self.assertNotIn('private reasoning', str(result['response_meta']))

    def test_chat_stream_returns_chunks_and_a_normalized_final_result(self):
        import model_router
        seen = []
        original = model_router.model_pool.http_stream
        def stream(_url, payload, _headers, _timeout, on_chunk, cancelled=None):
            self.assertNotIn('stream', payload)
            on_chunk('第一'); on_chunk('段')
            return {'ok': True, 'status': 200,
                    'data': {'choices': [{'message': {'content': '第一段'}}]}}
        model_router.model_pool.http_stream = stream
        try:
            result = _Adapter(key='sk-test').stream([], model='test-model', on_chunk=seen.append)
        finally:
            model_router.model_pool.http_stream = original
        self.assertTrue(result['ok'])
        self.assertEqual(seen, ['第一', '段'])
        self.assertEqual(result['text'], '第一段')

    def test_cancelled_stream_does_not_fall_back_to_a_second_request(self):
        import model_router
        original = model_router.model_pool.http_stream
        model_router.model_pool.http_stream = lambda *_args, **_kwargs: {'ok': False, 'status': 0, 'error': '请求已取消'}
        try:
            result = _Adapter(transport=lambda *_args: self.fail('取消后不得回退重发')).stream(
                [], model='test-model', on_chunk=lambda _chunk: None)
        finally:
            model_router.model_pool.http_stream = original
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_class'], 'cancelled')


if __name__ == '__main__':
    unittest.main()
