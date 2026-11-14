# -*- coding: utf-8 -*-
"""模型网关可靠性的零依赖单元测试：准入、Retry-After、流式生命周期与响应信封。"""
import io
import gzip
import tempfile
import unittest
import urllib.request
from email.message import Message
from pathlib import Path
from unittest.mock import patch

import model_pool
import model_router
from request_ledger import RequestLedger, record_request_attempt


class AdmissionTests(unittest.TestCase):
    def test_unattended_admission_requires_context_window(self):
        problem = model_pool.model_admission_error(
            {'label': '长文模型', 'model': 'm', 'base_url': 'https://x.test/v1', 'wire_api': 'chat'},
            require_context_length=True)
        self.assertIn('context_length', problem)

    def test_admission_accepts_a_valid_record(self):
        problem = model_pool.model_admission_error(
            {'model': 'm', 'base_url': 'https://x.test/v1', 'wire_api': 'chat', 'context_length': 64000},
            require_context_length=True)
        self.assertEqual(problem, '')


class RetryAfterTests(unittest.TestCase):
    def test_retry_after_seconds_and_date(self):
        headers = Message()
        headers['Retry-After'] = '3'
        self.assertEqual(model_pool._retry_after_seconds(headers), 3)

        headers = Message()
        headers['Retry-After'] = 'Wed, 21 Oct 2015 07:28:00 GMT'
        self.assertEqual(model_pool._retry_after_seconds(headers), 0)


class StreamLifecycleTests(unittest.TestCase):
    def stream(self, body):
        seen = []

        def respond(handler, request):
            response = urllib.response.addinfourl(io.BytesIO(body), Message(), request.full_url, 200)
            response.msg = 'OK'
            self.addCleanup(response.close)
            return response

        with patch('urllib.request._opener', None), \
                patch.object(urllib.request.HTTPSHandler, 'https_open', respond):
            result = model_pool.http_stream(
                'https://provider.invalid/v1/chat/completions',
                {'model': 'm', 'messages': []}, {}, 3, seen.append)
        return result, seen

    def test_stream_without_completion_event_is_rejected(self):
        import urllib.request
        body = (b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n')
        result, seen = self.stream(body)
        self.assertFalse(result['ok'])
        self.assertIn('完成事件', result['error'])
        self.assertEqual(seen, ['ok'])

    def test_stream_with_finish_reason_is_complete(self):
        import urllib.request
        body = (b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n')
        result, seen = self.stream(body)
        self.assertTrue(result['ok'])
        self.assertEqual(seen, ['ok'])


class EnvelopeTests(unittest.TestCase):
    def test_response_envelope_flags_missing_protocol_fields(self):
        self.assertTrue(model_router.response_envelope_error('chat', {}))
        self.assertTrue(model_router.response_envelope_error('responses', {'choices': []}))
        self.assertEqual(model_router.response_envelope_error('chat', {'choices': []}), '')


class HealthGateTests(unittest.TestCase):
    def test_failed_health_blocks_only_matching_config_version(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            record = model_pool.record({'model': 'm', 'base_url': 'https://x.test/v1', 'context_length': 8000})
            model_pool.record_health(record, {'ok': False, 'at': '1', 'config_version': model_pool.config_version(record)}, program)
            self.assertTrue(model_pool.health_is_blocked(record, program=program))
            record['base_url'] = 'https://x.test/v2'
            self.assertFalse(model_pool.health_is_blocked(record, program=program))

    def test_record_health_keeps_certification_checks(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            record = model_pool.record({'model': 'm', 'base_url': 'https://x.test/v1'})
            checks = [{'key': 'connectivity', 'ok': True}]
            entry = model_pool.record_health(record, {'ok': True, 'checks': checks}, program)
            self.assertEqual(entry['checks'], checks)


class RateLimitTests(unittest.TestCase):
    def test_bucket_spaces_requests(self):
        bucket = model_pool._RateBucket(2)
        self.assertEqual(bucket.wait(0.0), 0.0)
        self.assertAlmostEqual(bucket.wait(0.0), 30.0)


class DecodeTests(unittest.TestCase):
    def test_gzip_body_is_decoded_with_limit(self):
        raw = gzip.compress('{"ok":true}'.encode('utf-8'))
        headers = Message()
        headers['Content-Encoding'] = 'gzip'
        self.assertEqual(model_pool._decode_response_body(raw, headers, 1024), b'{"ok":true}')


class RequestAttemptTests(unittest.TestCase):
    def test_record_attempt_appends_without_changing_state(self):
        ledger = RequestLedger()
        ledger.reserve('r1', 'tokens', 10)
        record_request_attempt(ledger, 'r1', status=429, error_class='rate_limit', retry_count=1)
        self.assertEqual(ledger._find('r1')['attempts'][0]['status'], 429)
        self.assertEqual(ledger._find('r1')['state'], 'reserved')


class GatewayTests(unittest.TestCase):
    def test_gateway_falls_back_across_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            (program / '.env').write_text('K=sk-test-1\n', encoding='utf-8')
            records = {
                'a': {'model': 'a', 'base_url': 'https://x.test/v1', 'key_env': 'K', 'context_length': 8000},
                'b': {'model': 'b', 'base_url': 'https://x.test/v1', 'key_env': 'K', 'context_length': 8000},
            }
            calls = []

            def transport(url, payload, headers, timeout):
                calls.append(payload.get('model'))
                if payload.get('model') == 'a':
                    return {'ok': False, 'status': 429, 'error': 'HTTP 429：限流'}
                return {'ok': True, 'status': 200, 'data': {'choices': [{'message': {'content': '好'}}]}}

            gateway = model_router.ModelGateway(program=program, transport=transport, records=records)
            result = gateway.chat(['a', 'b'], [{'role': 'user', 'content': 'hi'}], options={'max_tokens': 16})
            self.assertTrue(result['ok'])
            self.assertEqual(result['text'], '好')
            self.assertEqual(calls, ['a', 'b'])


class GroupCandidatesTests(unittest.TestCase):
    def test_group_candidates_puts_current_first(self):
        records = {
            'a': {'model': 'a', 'group': 'primary'},
            'b': {'model': 'b', 'group': 'primary'},
            'c': {'model': 'c', 'group': 'other'},
        }
        self.assertEqual(model_pool.group_candidates('primary', 'b', records=records), ['b', 'a'])

    def test_group_candidates_respects_weight(self):
        records = {
            'a': {'model': 'a', 'group': 'primary', 'weight': '5'},
            'b': {'model': 'b', 'group': 'primary', 'weight': '1'},
        }
        self.assertEqual(model_pool.group_candidates('primary', 'b', records=records), ['a', 'b'])

    def test_gateway_for_group_uses_current_first(self):
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            (program / '.env').write_text('K=sk-test-1\n', encoding='utf-8')
            records = {
                'a': {'model': 'a', 'base_url': 'https://x.test/v1', 'key_env': 'K', 'group': 'primary'},
                'b': {'model': 'b', 'base_url': 'https://x.test/v1', 'key_env': 'K', 'group': 'primary'},
            }
            calls = []

            def transport(url, payload, headers, timeout):
                calls.append(payload.get('model'))
                return {'ok': True, 'status': 200, 'data': {'choices': [{'message': {'content': '好'}}]}}

            gateway = model_router.ModelGateway.for_group(
                'primary', 'b', records=records, program=program, transport=transport)
            result = gateway.chat_group([{'role': 'user', 'content': 'hi'}], options={'max_tokens': 16})
            self.assertTrue(result['ok'])
            self.assertEqual(calls[0], 'b')


class CircuitBreakerTests(unittest.TestCase):
    def test_opens_after_threshold_and_half_opens_after_cooldown(self):
        model_router.record_circuit_success('breaker-test')
        for _ in range(model_router.CIRCUIT_FAILURE_THRESHOLD):
            model_router.record_circuit_failure('breaker-test')
        self.assertEqual(model_router.circuit_state('breaker-test')['state'], 'open')
        self.assertFalse(model_router.circuit_allows('breaker-test'))
        model_router._CIRCUITS['breaker-test'].opened_at -= model_router.CIRCUIT_COOLDOWN_SECONDS + 1
        self.assertEqual(model_router.circuit_state('breaker-test')['state'], 'half_open')
        self.assertTrue(model_router.circuit_allows('breaker-test'))
        model_router.record_circuit_success('breaker-test')
        self.assertEqual(model_router.circuit_state('breaker-test')['state'], 'closed')


if __name__ == '__main__':
    unittest.main()
