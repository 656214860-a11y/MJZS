"""http_client 弹性层契约：超时必填、错误码分类、有界重试、响应上限、凭据脱敏。"""
import io
import unittest
import urllib.error
import urllib.request

from infra import http_client
from contract.error_codes import code_of


class _Resp:
    def __init__(self, body=b'{"ok": true}', status=200, headers=None):
        self._body = io.BytesIO(body)
        self.status = status
        self.headers = headers or {}

    def read(self, n=-1):
        return self._body.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Opener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _http_error(code, body=b'{"error": {"code": "x"}}'):
    return urllib.error.HTTPError('http://h/', code, 'err', {}, io.BytesIO(body))


class RequestJsonTests(unittest.TestCase):
    def setUp(self):
        http_client._HOST_FAILURES.clear()

    def test_success_returns_parsed_json_and_status(self):
        opener = _Opener([_Resp(b'{"a": 1}')])
        result = http_client.request_json('GET', 'http://h/x', timeout=5, opener=opener)
        self.assertTrue(result.ok)
        self.assertEqual(result.data['json'], {'a': 1})
        self.assertEqual(result.data['status'], 200)
        self.assertEqual(opener.calls[0][1], 5)

    def test_post_payload_marks_method_and_never_retries_by_default(self):
        opener = _Opener([_http_error(500), _Resp(b'{}')])
        result = http_client.request_json('POST', 'http://h/x', payload={'a': 1},
                                          timeout=5, retries=3, opener=opener, sleep=lambda s: None)
        self.assertFalse(result.ok)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(opener.calls[0][0].get_method(), 'POST')
        self.assertEqual(code_of(result), 'E-NET-SERVER')

    def test_get_retries_retryable_status_with_backoff(self):
        opener = _Opener([_http_error(503), _Resp(b'{"a": 2}')])
        sleeps = []
        result = http_client.request_json('GET', 'http://h/x', timeout=5, retries=2,
                                          opener=opener, sleep=sleeps.append)
        self.assertTrue(result.ok)
        self.assertEqual(len(opener.calls), 2)
        self.assertEqual(len(sleeps), 1)

    def test_429_classifies_rate_limit_and_honors_retry(self):
        opener = _Opener([_http_error(429), _Resp(b'{}')])
        result = http_client.request_json('GET', 'http://h/x', timeout=5, retries=1,
                                          opener=opener, sleep=lambda s: None)
        self.assertTrue(result.ok)
        self.assertEqual(len(opener.calls), 2)

    def test_client_error_is_not_retryable(self):
        opener = _Opener([_http_error(400), _Resp(b'{}')])
        result = http_client.request_json('GET', 'http://h/x', timeout=5, retries=3,
                                          opener=opener, sleep=lambda s: None)
        self.assertFalse(result.ok)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(code_of(result), 'E-NET-CLIENT')
        self.assertFalse(result.recoverable)

    def test_auth_error_maps_to_auth_code(self):
        opener = _Opener([_http_error(401)])
        result = http_client.request_json('GET', 'http://h/x', timeout=5, opener=opener)
        self.assertEqual(code_of(result), 'E-AUTH-REJECTED')

    def test_timeout_maps_to_net_timeout(self):
        opener = _Opener([urllib.error.URLError('timed out')])
        result = http_client.request_json('GET', 'http://h/x', timeout=5, retries=0, opener=opener)
        self.assertFalse(result.ok)
        self.assertEqual(code_of(result), 'E-NET-TIMEOUT')

    def test_unreachable_maps_and_retries(self):
        opener = _Opener([urllib.error.URLError('connection refused'), _Resp(b'{}')])
        result = http_client.request_json('GET', 'http://h/x', timeout=5, retries=1,
                                          opener=opener, sleep=lambda s: None)
        self.assertTrue(result.ok)
        self.assertEqual(code_of(result), '')

    def test_response_over_limit_rejected(self):
        opener = _Opener([_Resp(b'x' * 100, headers={'Content-Length': '100'})])
        result = http_client.request_json('GET', 'http://h/x', timeout=5, max_bytes=10, opener=opener)
        self.assertFalse(result.ok)
        self.assertIn('上限', result.data['error_body'])

    def test_sensitive_headers_redacted_in_result(self):
        # 脱敏走 _safe_headers：响应/错误头里的 Authorization 等一律 [REDACTED]
        self.assertEqual(http_client._safe_headers({'Authorization': 'k', 'X-Ok': 'v'}),
                         {'Authorization': '[REDACTED]', 'X-Ok': 'v'})

    def test_circuit_breaker_opens_after_threshold_failures(self):
        opener = _Opener([urllib.error.URLError('down')] * 10)
        for _ in range(http_client._CIRCUIT_THRESHOLD):
            http_client.request_json('GET', 'http://cb-host/x', timeout=1, opener=opener)
        before = len(opener.calls)
        result = http_client.request_json('GET', 'http://cb-host/x', timeout=1, opener=opener)
        self.assertFalse(result.ok)
        self.assertEqual(code_of(result), 'E-NET-UNREACHABLE')
        self.assertEqual(len(opener.calls), before)


if __name__ == '__main__':
    unittest.main()
