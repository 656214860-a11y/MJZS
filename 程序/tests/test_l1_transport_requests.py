"""L1 轮 5：传输层收敛 RequestsJsonOpener 的验收测试（R5-a~g）。"""
import gzip
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from contract import platform_tools
from infra import api_endpoints, comfy_service, seedream_api

PROGRAM_DIR = Path(__file__).resolve().parent.parent


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def _record(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else b''
        self.server.calls.append((self.command, self.path, dict(self.headers), body))

    def do_GET(self):
        self._record()
        route = self.server.routes.get(self.path)
        self._respond(route(self) if callable(route) else route)

    def do_POST(self):
        self._record()
        route = self.server.routes.get(self.path)
        self._respond(route(self) if callable(route) else route)

    def _respond(self, route):
        status, headers, body = route if isinstance(route, tuple) else (200, {}, b'{"ok": true}')
        payload = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(payload)


class _Server:
    def __init__(self, routes=None):
        self.routes = routes or {}
        self.calls = []
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        self.httpd.routes, self.httpd.calls = self.routes, self.calls
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:%d' % self.httpd.server_address[1]

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


class TransportConvergenceTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {'DRAMA_SUPPRESS_NETWORK': '0'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.server = _Server()
        self.addCleanup(self.server.close)

    def test_loopback_bypasses_proxy_environment(self):
        env = {'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9',
               'http_proxy': 'http://127.0.0.1:9', 'https_proxy': 'http://127.0.0.1:9',
               'NO_PROXY': '', 'no_proxy': ''}
        with mock.patch.dict(os.environ, env, clear=False):
            with platform_tools.RequestsJsonOpener().open(
                    urllib.request.Request(self.server.base + '/ok'), timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read()), {'ok': True})
        self.assertEqual(len(self.server.calls), 1)

    def test_localhost_hostname_bypasses_proxy_and_transport_converged(self):
        env = {'HTTPS_PROXY': 'http://127.0.0.1:9', 'https_proxy': 'http://127.0.0.1:9',
               'NO_PROXY': '', 'no_proxy': ''}
        with mock.patch.dict(os.environ, env, clear=False):
            result = api_endpoints._http_transport(
                self.server.base.replace('127.0.0.1', 'localhost') + '/ok', {'q': 1}, {}, 5)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['data'], {'ok': True})

    def test_decompressed_body_over_limit_rejected(self):
        blob = gzip.compress(b' ' * 8192)
        self.server.routes['/gzip'] = (200, {'Content-Encoding': 'gzip'}, blob)
        self.assertLess(len(blob), 256)
        with mock.patch.object(api_endpoints, 'RESPONSE_BODY_MAX_BYTES', 1024):
            result = api_endpoints._http_transport(self.server.base + '/gzip', {'q': 1}, {}, 5)
        self.assertFalse(result['ok'])
        self.assertIn('上限', result['error'])

    def test_identity_response_keeps_content_length_semantics(self):
        result = api_endpoints._http_transport(self.server.base + '/ok', {'q': 1}, {}, 5)
        self.assertTrue(result['ok'], result)

    def test_cross_host_redirect_never_forwards_api_key(self):
        target = _Server()
        self.addCleanup(target.close)
        self.server.routes['/hop'] = (302, {'Location': target.base + '/landing'}, b'')
        request = urllib.request.Request(self.server.base + '/hop',
                                         headers={'X-Api-Key': 'SYNTHETIC_SECRET'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            platform_tools.RequestsJsonOpener().open(request, timeout=5)
        self.assertEqual(caught.exception.code, 302)
        self.assertEqual(target.calls, [])
        self.assertNotIn('SYNTHETIC_SECRET', repr(caught.exception))

    def test_response_iteration_yields_lines_for_stream_consumers(self):
        body = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'
        self.server.routes['/sse'] = (200, {'Content-Type': 'text/event-stream'}, body)
        seen = []
        result = api_endpoints.http_stream(
            self.server.base + '/sse', {'model': 'm', 'messages': []}, {}, 5, seen.append)
        self.assertTrue(result['ok'], result)
        self.assertEqual(''.join(seen), 'hi')

    def test_comfy_and_seedream_route_through_requests_opener(self):
        with mock.patch.object(platform_tools, 'RequestsJsonOpener') as factory:
            factory.return_value.open.side_effect = urllib.error.URLError('stop')
            with self.assertRaises(urllib.error.URLError):
                comfy_service.Comfy('http://127.0.0.1:9').request('/object_info')
            factory.return_value.open.assert_called_once()
        with mock.patch.object(platform_tools, 'RequestsJsonOpener') as factory:
            factory.return_value.open.side_effect = urllib.error.URLError('stop')
            profile = {'api_key': 'k', 'base_url': 'http://127.0.0.1:9'}
            with self.assertRaises(seedream_api.Uncertain):
                seedream_api.request_image(profile, {'model': 'm', 'prompt': 'p'})
            factory.return_value.open.assert_called_once()

    def test_desktop_import_does_not_load_requests(self):
        code = ('import sys; sys.path.insert(0, %r); import desktop; '
                'sys.exit(0 if "requests" not in sys.modules and "urllib3" not in sys.modules else 3)'
                % str(PROGRAM_DIR))
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=str(PROGRAM_DIR),
                                env=env, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-500:])

    def test_selfsigned_https_untrusted_fails_readably(self):
        openssl = shutil.which('openssl')
        self.assertIsNotNone(openssl, '验收环境需要 openssl 签发自签证书')
        with tempfile.TemporaryDirectory() as folder:
            key, cert = Path(folder) / 'k.pem', Path(folder) / 'c.pem'
            subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=localhost'], check=True, capture_output=True, timeout=60)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(cert), str(key))
            httpd = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
            httpd.routes, httpd.calls = {'/ok': (200, {}, b'{}')}, []
            raw = httpd.socket
            httpd.socket = context.wrap_socket(raw, server_side=True)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(httpd.server_close)
            self.addCleanup(httpd.shutdown)
            port = httpd.server_address[1]
            with self.assertRaises((urllib.error.URLError, TimeoutError, OSError)) as caught:
                platform_tools.RequestsJsonOpener().open(
                    urllib.request.Request('https://localhost:%d/ok' % port), timeout=10)
            self.assertNotIn('k.pem', str(caught.exception))
            self.assertFalse(httpd.calls)  # TLS 握手失败，请求未到达应用层


if __name__ == '__main__':
    unittest.main()
