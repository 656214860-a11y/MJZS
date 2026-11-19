"""http_client 弹性层契约：超时必填、错误码分类、有界重试、响应上限、凭据脱敏。"""
import gzip
import io
import json
import os
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from contract import platform_tools
import requests
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


class RequestBytesTests(unittest.TestCase):
    """request_bytes：与 request_json 同一传输内核，成功 data 带原始字节 ``body``。"""

    def setUp(self):
        http_client._HOST_FAILURES.clear()

    def test_success_returns_raw_bytes_without_text_decoding(self):
        body = b'\x89PNG\r\n\x1a\n\xff\xfe\x00binary'
        opener = _Opener([_Resp(body, headers={'X-Kind': 'audio/mpeg'})])
        result = http_client.request_bytes('GET', 'http://h/x', timeout=5, opener=opener)
        self.assertTrue(result.ok)
        self.assertEqual(result.data['body'], body)
        self.assertEqual(result.data['status'], 200)
        self.assertEqual(result.data['headers']['X-Kind'], 'audio/mpeg')
        self.assertNotIn('text', result.data)
        self.assertNotIn('json', result.data)

    def test_payload_marks_post_and_sends_json_body(self):
        opener = _Opener([_Resp(b'audio')])
        result = http_client.request_bytes('POST', 'http://h/x',
                                           payload={'input': '你好'},
                                           headers={'Authorization': 'Bearer k'},
                                           timeout=5, opener=opener)
        self.assertTrue(result.ok)
        request = opener.calls[0][0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(json.loads(request.data.decode('utf-8')), {'input': '你好'})
        sent = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(sent.get('content-type'), 'application/json')
        self.assertEqual(sent.get('authorization'), 'Bearer k')

    def test_post_never_retries_by_default(self):
        opener = _Opener([_http_error(500), _Resp(b'ok')])
        result = http_client.request_bytes('POST', 'http://h/x', payload={'a': 1},
                                           timeout=5, retries=3, opener=opener,
                                           sleep=lambda s: None)
        self.assertFalse(result.ok)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(code_of(result), 'E-NET-SERVER')

    def test_http_error_classifies_with_status_and_body(self):
        opener = _Opener([_http_error(429, b'{"error": "slow down"}')])
        result = http_client.request_bytes('POST', 'http://h/x', payload={},
                                           timeout=5, opener=opener)
        self.assertFalse(result.ok)
        self.assertEqual(code_of(result), 'E-NET-RATE-LIMIT')
        self.assertEqual(result.data['status'], 429)
        self.assertIn('slow down', result.data['error_body'])

    def test_timeout_and_unreachable_classify(self):
        opener = _Opener([TimeoutError('timed out'), urllib.error.URLError('connection refused')])
        first = http_client.request_bytes('GET', 'http://h/x', timeout=5, opener=opener)
        second = http_client.request_bytes('GET', 'http://h/y', timeout=5, opener=opener)
        self.assertEqual(code_of(first), 'E-NET-TIMEOUT')
        self.assertEqual(code_of(second), 'E-NET-UNREACHABLE')

    def test_body_over_limit_rejected(self):
        opener = _Opener([_Resp(b'x' * 100)])
        result = http_client.request_bytes('GET', 'http://h/x', timeout=5,
                                           max_bytes=10, opener=opener)
        self.assertFalse(result.ok)
        self.assertIn('上限', result.data['error_body'])

    def test_circuit_breaker_shared_across_entry_points(self):
        opener = _Opener([urllib.error.URLError('down')] * 10)
        for _ in range(http_client._CIRCUIT_THRESHOLD):
            http_client.request_bytes('GET', 'http://cb-shared/x', timeout=1, opener=opener)
        before = len(opener.calls)
        blocked = http_client.request_bytes('GET', 'http://cb-shared/x', timeout=1, opener=opener)
        blocked_json = http_client.request_json('GET', 'http://cb-shared/x', timeout=1, opener=opener)
        self.assertEqual(code_of(blocked), 'E-NET-UNREACHABLE')
        self.assertEqual(code_of(blocked_json), 'E-NET-UNREACHABLE')
        self.assertEqual(len(opener.calls), before)

    def test_timeout_is_mandatory(self):
        with self.assertRaises(TypeError):
            http_client.request_bytes('GET', 'http://h/x')


class RequestsTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                self.do_GET()

            def do_GET(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                self.server.calls.append((self.command, self.path, dict(self.headers), body))
                path = self.path
                if path in ('/disconnect', '/images/generations'):
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                if path == '/timeout':
                    self.server.release.wait(0.3)
                status, data, headers = 200, b'{"ok": true}', {}
                if path.startswith('/redirect/'):
                    status = int(path.rsplit('/', 1)[1])
                    headers['Location'] = self.server.target
                elif path == '/retry' and sum(c[1] == path for c in self.server.calls) == 1:
                    status = 503
                elif path == '/retry501' and sum(c[1] == path for c in self.server.calls) == 1:
                    status = 501
                elif path == '/busy':
                    status = 503
                elif path == '/throttled':
                    status = 429
                    headers['Retry-After'] = '7200'
                elif path == '/error':
                    status, data = 500, b'x' * (http_client.ERROR_BODY_MAX_BYTES + 4096)
                elif path == '/gzip':
                    data = gzip.compress(b'x' * 100000)
                    headers['Content-Encoding'] = 'gzip'
                elif path == '/audio':
                    # 含非法 UTF-8 字节的二进制响应：request_bytes 必须原样返回，不能经文本解码。
                    status, data = 200, b'\x00\xff\xfe\x89PNG-audio-bytes'
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header('Authorization', 'response-secret')
                self.send_header('Content-Length', str(len(data) + (100 if path == '/truncated' else 0)))
                self.end_headers()
                if path == '/read-timeout':
                    self.server.release.wait(0.3)
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

        cls.servers = []
        for _ in range(2):
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            server.calls, server.release = [], threading.Event()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.servers.append((server, thread))
        cls.server = cls.servers[0][0]
        cls.base = 'http://127.0.0.1:%d' % cls.server.server_port
        cls.server.target = 'http://127.0.0.1:%d/target' % cls.servers[1][0].server_port

    @classmethod
    def tearDownClass(cls):
        for server, thread in cls.servers:
            server.release.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def setUp(self):
        http_client._HOST_FAILURES.clear()
        for server, _ in self.servers:
            server.calls.clear()
        self.env = mock.patch.dict(os.environ, {'DRAMA_SUPPRESS_NETWORK': '0', 'NO_PROXY': '*'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.sessions, self.responses = [], []
        session_type = requests.Session
        real_send = requests.adapters.HTTPAdapter.send

        def send(adapter, *args, **kwargs):
            response = real_send(adapter, *args, **kwargs)
            response.close = mock.Mock(wraps=response.close)
            response.raw.read = mock.Mock(wraps=response.raw.read)
            self.responses.append(response)
            return response

        def session():
            result = session_type()
            result.close = mock.Mock(wraps=result.close)
            self.sessions.append(result)
            return result

        patcher = mock.patch.object(requests.adapters.HTTPAdapter, 'send', autospec=True, side_effect=send)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(requests, 'Session', side_effect=session)
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, path, method='GET', **opts):
        return http_client.request_json(method, self.base + path, timeout=opts.pop('timeout', 1), **opts)

    def assert_closed(self):
        self.assertTrue(self.sessions, '默认传输必须实际使用 requests.Session')
        for session in self.sessions:
            session.close.assert_called_once()
        for response in self.responses:
            response.close.assert_called_once()
            self.assertTrue(response.raw.closed)

    def test_default_uses_requests_and_preserves_explicit_headers_without_netrc(self):
        with mock.patch('requests.sessions.get_netrc_auth', return_value=('netrc-user', 'netrc-secret')) as netrc:
            result = self.call('/ok', headers={'Authorization': 'Bearer explicit', 'Cookie': 'keep=1'})
        self.assertTrue(result.ok)
        self.assertEqual(self.server.calls[0][2]['Authorization'], 'Bearer explicit')
        self.assertEqual(self.server.calls[0][2]['Cookie'], 'keep=1')
        netrc.assert_not_called()
        self.assertEqual(result.data['headers']['Authorization'], '[REDACTED]')
        self.assertTrue(self.sessions[0].trust_env)
        for session in self.sessions:
            for adapter in session.adapters.values():
                retry = adapter.max_retries
                self.assertEqual(retry.total, 0)
        self.assert_closed()

    def test_effective_get_and_payload_force_post(self):
        self.assertTrue(self.call('/ok', method='get').ok)
        self.assertTrue(self.call('/ok', payload={'中文': 2}).ok)
        self.assertTrue(self.call('/ok', method='POST').ok)
        self.assertEqual([c[0] for c in self.server.calls], ['GET', 'POST', 'POST'])
        self.assertEqual(json.loads(self.server.calls[1][3]), {'中文': 2})
        self.assert_closed()

    def test_get_retryable_status_retries_in_http_loop(self):
        waits = []
        result = self.call('/retry', retries=1, sleep=waits.append)
        self.assertTrue(result.ok)
        self.assertEqual(len(self.server.calls), 2)
        self.assertEqual(len(waits), 1)
        self.assert_closed()

    def test_get_non_forcelist_status_still_retries_in_business_loop(self):
        waits = []
        result = self.call('/retry501', retries=1, retry_statuses={501}, sleep=waits.append)
        self.assertTrue(result.ok)
        self.assertEqual(len(self.server.calls), 2)
        self.assertEqual(len(waits), 1)
        self.assert_closed()

    def test_model_get_spends_only_the_shared_budget(self):
        from infra import api_endpoints

        budget = [2]
        with mock.patch.object(api_endpoints, '_SLEEP'):
            result = api_endpoints.http_transport(self.base + '/busy', None, {}, 1,
                                                  attempt_budget=budget)
        self.assertFalse(result['ok'])
        self.assertEqual(budget, [0])
        self.assertEqual(len(self.server.calls), 2)
        self.assert_closed()

    def test_pre_cancelled_execution_sends_no_http_request(self):
        control = platform_tools.ExecutionControl(timeout=5)
        control.cancel()
        with platform_tools.execution_scope(control):
            with self.assertRaisesRegex(platform_tools.ExecutionStopped, 'cancelled'):
                self.call('/ok')
        self.assertEqual(self.server.calls, [])

    def test_persistent_503_uses_only_the_configured_http_budget(self):
        result = self.call('/busy', retries=2, sleep=lambda _: None)
        self.assertFalse(result.ok)
        self.assertEqual(len(self.server.calls), 3)
        self.assertEqual(result.data['retry_count'], 2)
        self.assert_closed()

    def test_cancel_during_backoff_prevents_another_http_request(self):
        control = platform_tools.ExecutionControl(timeout=5)
        with platform_tools.execution_scope(control):
            with self.assertRaisesRegex(platform_tools.ExecutionStopped, 'cancelled'):
                self.call('/busy', retries=2, sleep=lambda _: control.cancel())
        self.assertEqual(len(self.server.calls), 1)
        self.assert_closed()

    def test_retry_after_beyond_deadline_cannot_send_another_request(self):
        control = platform_tools.ExecutionControl(timeout=5)
        waits = []

        def advance(seconds):
            waits.append(seconds)
            control.deadline = platform_tools.time.monotonic() - 1

        with platform_tools.execution_scope(control):
            with self.assertRaisesRegex(platform_tools.ExecutionStopped, 'deadline'):
                self.call('/throttled', retries=2, sleep=advance)
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual(len(waits), 1)
        self.assertGreater(waits[0], 0)
        self.assertLessEqual(waits[0], 5)
        self.assert_closed()

    def test_ambiguous_paid_post_disconnect_is_unknown_and_never_repeated(self):
        result = self.call('/disconnect', payload={}, retries=3)
        self.assertFalse(result.ok)
        self.assertFalse(result.recoverable)
        self.assertEqual(result.data['acceptance'], 'unknown')
        self.assertEqual(result.data['retry_count'], 0)
        self.assertEqual([call[0] for call in self.server.calls], ['POST'])
        self.assert_closed()

    def test_seedream_lost_receipt_is_uncertain_after_one_paid_submission(self):
        from infra import seedream_api

        profile = {'api_key': 'local-only', 'base_url': self.base}
        with self.assertRaises(seedream_api.Uncertain):
            seedream_api.request_image(profile, {'model': 'local-test'})
        self.assertEqual([(call[0], call[1]) for call in self.server.calls],
                         [('POST', '/images/generations')])
        self.assert_closed()

    def test_post_never_repeats_without_explicit_permission(self):
        result = self.call('/retry', method='POST', retries=3)
        self.assertEqual(code_of(result), 'E-NET-SERVER')
        self.assertEqual(len(self.server.calls), 1)
        self.assert_closed()

    def test_post_explicit_permission_retries(self):
        result = self.call('/retry', payload={}, retries=1, allow_retry_post=True, sleep=lambda _: None)
        self.assertTrue(result.ok)
        self.assertEqual([c[0] for c in self.server.calls], ['POST', 'POST'])
        self.assert_closed()

    def test_redirects_and_other_3xx_match_no_redirect_without_forwarding(self):
        for method in ('GET', 'POST'):
            for status in (300, 301, 302, 303, 304, 305, 307, 308, 399):
                with self.subTest(method=method, status=status):
                    result = self.call('/redirect/%d' % status, method=method, retries=2,
                                       headers={'Authorization': 'secret', 'Cookie': 'secret'})
                    self.assertFalse(result.ok)
                    self.assertEqual(result.data['status'], status)
                    self.assertEqual(code_of(result), 'E-NET-CLIENT')
        self.assertEqual(len(self.server.calls), 18)
        self.assertEqual(self.servers[1][0].calls, [])
        self.assert_closed()

    def test_gzip_is_decompressed_with_bounded_reads_and_closed_on_limit(self):
        result = self.call('/gzip', max_bytes=256)
        self.assertFalse(result.ok)
        self.assertIn('上限', result.data['error_body'])
        self.assert_closed()
        for call in self.responses[0].raw.read.call_args_list:
            self.assertLessEqual(call.args[0], 257)
            self.assertTrue(call.kwargs['decode_content'])

    def test_error_body_is_bounded_and_http_error_is_closed(self):
        result = self.call('/error')
        self.assertEqual(code_of(result), 'E-NET-SERVER')
        self.assertEqual(len(result.data['error_body']), http_client.ERROR_BODY_MAX_BYTES)
        self.assertEqual(result.data['headers']['Authorization'], '[REDACTED]')
        self.assert_closed()
        self.responses[0].raw.read.assert_called_once_with(http_client.ERROR_BODY_MAX_BYTES, decode_content=True)

    def test_request_bytes_returns_exact_binary_body(self):
        result = http_client.request_bytes('GET', self.base + '/audio', timeout=1)
        self.assertTrue(result.ok)
        self.assertEqual(result.data['body'], b'\x00\xff\xfe\x89PNG-audio-bytes')
        self.assertEqual(result.data['status'], 200)
        self.assertNotIn('text', result.data)
        self.assert_closed()

    def test_request_bytes_post_carries_json_payload(self):
        result = http_client.request_bytes('POST', self.base + '/audio',
                                           payload={'input': '你好'}, timeout=1)
        self.assertTrue(result.ok)
        self.assertEqual(json.loads(self.server.calls[0][3])['input'], '你好')
        self.assert_closed()

    def test_timeout_disconnect_and_read_failure_are_normalized_and_closed(self):
        for path, expected in (('/timeout', 'E-NET-TIMEOUT'), ('/read-timeout', 'E-NET-TIMEOUT'),
                               ('/disconnect', 'E-NET-UNREACHABLE'), ('/truncated', 'E-NET-UNREACHABLE')):
            with self.subTest(path=path):
                result = self.call(path, timeout=0.05)
                self.assertFalse(result.ok)
                self.assertEqual(code_of(result), expected)
        self.assert_closed()

    def test_default_connection_failure_does_not_expose_url_query(self):
        url = 'http://127.0.0.1:1?api_key=SYNTHETIC_SECRET'
        result = http_client.request_json('GET', url, timeout=3)
        self.assertFalse(result.ok)
        self.assertEqual(code_of(result), 'E-NET-UNREACHABLE')
        for exposed in (repr(result), result.data['error_body']):
            self.assertNotIn('SYNTHETIC_SECRET', exposed)
            self.assertNotIn('api_key=', exposed)
            self.assertNotIn(url, exposed)
        self.assert_closed()

    def test_default_invalid_header_does_not_expose_header_value(self):
        value = '\nBearer SYNTHETIC_HEADER_TOKEN'
        result = self.call('/ok', headers={'Authorization': value})
        self.assertFalse(result.ok)
        self.assertEqual(code_of(result), 'E-NET-UNREACHABLE')
        for exposed in (repr(result), result.data['error_body']):
            self.assertNotIn('SYNTHETIC_HEADER_TOKEN', exposed)
            self.assertNotIn('Bearer', exposed)
            self.assertNotIn('Authorization', exposed)
        self.assertEqual(self.server.calls, [])
        self.assert_closed()

    def test_default_timeout_does_not_expose_transport_exception_details(self):
        detail = ('https://example.invalid/?api_key=SYNTHETIC_SECRET '
                  'Authorization: Bearer SYNTHETIC_HEADER_TOKEN '
                  'http://SYNTHETIC_PROXY_USER:SYNTHETIC_PROXY_PASSWORD@proxy.invalid')
        for error_type in (requests.exceptions.Timeout, TimeoutError):
            with self.subTest(error_type=error_type):
                http_client._HOST_FAILURES.clear()
                error = error_type(detail)
                with mock.patch.object(requests.adapters.HTTPAdapter, 'send', side_effect=error):
                    result = self.call('/ok')
                self.assertFalse(result.ok)
                self.assertEqual(code_of(result), 'E-NET-TIMEOUT')
                for exposed in (repr(result), result.data['error_body']):
                    for credential in ('SYNTHETIC_SECRET', 'api_key=', 'example.invalid',
                                       'SYNTHETIC_HEADER_TOKEN', 'Authorization',
                                       'SYNTHETIC_PROXY_USER', 'SYNTHETIC_PROXY_PASSWORD',
                                       'proxy.invalid'):
                        self.assertNotIn(credential, exposed)
        self.assertEqual(self.server.calls, [])
        self.assert_closed()

    def test_default_read_timeout_keeps_cause_private(self):
        from urllib3.exceptions import TimeoutError as ReadTimeout
        error = ReadTimeout('https://example.invalid/?api_key=SYNTHETIC_SECRET')
        response = mock.Mock(status_code=200, headers={})
        response.raw.read.side_effect = error
        with mock.patch.object(requests.adapters.HTTPAdapter, 'send', return_value=response):
            result = self.call('/ok')
            with platform_tools.RequestsJsonOpener().open(
                    urllib.request.Request(self.base + '/ok'), timeout=1) as opened:
                with self.assertRaises(TimeoutError) as caught:
                    opened.read(1)
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(code_of(result), 'E-NET-TIMEOUT')
        for exposed in (repr(result), result.data['error_body'], str(caught.exception)):
            self.assertNotIn('SYNTHETIC_SECRET', exposed)
            self.assertNotIn('api_key=', exposed)
            self.assertNotIn('example.invalid', exposed)
        self.assert_closed()

    def test_network_suppression_prevents_default_connection(self):
        with mock.patch.dict(os.environ, {'DRAMA_SUPPRESS_NETWORK': '1'}):
            result = self.call('/ok')
        self.assertEqual(code_of(result), 'E-NET-UNREACHABLE')
        self.assertEqual(self.server.calls, [])
        self.assertEqual(self.sessions, [])

    def test_platform_adapter_merges_environment_proxy_and_keeps_tls_verification(self):
        response = mock.Mock(status_code=200, headers={}, raw=io.BytesIO(b'{}'))
        settings = {'proxies': {'https': 'http://local-proxy:3128'}, 'verify': True,
                    'cert': None, 'stream': True}
        with mock.patch.object(requests.sessions.Session, 'merge_environment_settings', return_value=settings) as merge:
            with mock.patch.object(requests.adapters.HTTPAdapter, 'send', return_value=response) as send:
                with platform_tools.RequestsJsonOpener().open(
                        urllib.request.Request('https://example.invalid/json'), timeout=7):
                    pass
        merge.assert_called_once_with('https://example.invalid/json', {}, True, True, None)
        self.assertEqual(send.call_args.kwargs, dict(settings, timeout=7))
        self.assertEqual(send.call_args.args[0].method, 'GET')
        response.close.assert_called_once()
        self.assert_closed()

    def test_platform_adapter_uses_real_environment_proxy_settings(self):
        response = mock.Mock(status_code=200, headers={})
        env = {'HTTPS_PROXY': 'http://local-proxy:3128', 'NO_PROXY': ''}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(requests.adapters.HTTPAdapter, 'send', return_value=response) as send:
                with platform_tools.RequestsJsonOpener().open(
                        urllib.request.Request('https://example.invalid/json'), timeout=7):
                    pass
        self.assertEqual(send.call_args.kwargs['proxies']['https'], 'http://local-proxy:3128')
        self.assertIs(send.call_args.kwargs['verify'], True)
        self.assertIs(send.call_args.kwargs['stream'], True)
        response.close.assert_called_once()
        self.assert_closed()

    def test_declared_oversize_and_http_error_read_failure_close_resources(self):
        result = self.call('/ok', max_bytes=2)
        self.assertFalse(result.ok)
        self.responses[0].raw.read.assert_not_called()
        with mock.patch.object(self.server, 'target', self.base + '/target'):
            result = self.call('/redirect/302')
        self.assertFalse(result.ok)
        self.assert_closed()
        error = _http_error(500)
        with mock.patch.object(error, 'read', side_effect=OSError('broken read')):
            result = http_client.request_json('GET', self.base, timeout=1, opener=_Opener([error]))
        self.assertFalse(result.ok)
        self.assertTrue(error.fp.closed)

    def test_injected_urllib_http_error_stream_is_closed(self):
        stream = io.BytesIO(b'{"error": 1}')
        error = urllib.error.HTTPError(self.base, 400, 'bad', {}, stream)
        result = http_client.request_json('GET', self.base, timeout=1, opener=_Opener([error]))
        self.assertFalse(result.ok)
        self.assertTrue(stream.closed)


if __name__ == '__main__':
    unittest.main()
