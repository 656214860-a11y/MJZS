# -*- coding: utf-8 -*-
"""R2178 J13／J14：重定向拒绝与子进程登记各只有一份实现，各适配器共用。"""
import io
import subprocess
import urllib.error
import urllib.request
import urllib.response
from email.message import Message

import requests
from urllib3.response import HTTPResponse
import sys
import unittest
from unittest import mock
from urllib.request import HTTPRedirectHandler

import infra.api_endpoints as api_endpoints
import local_video
import seedream_api
from domain import tts_api
import workflow_engines
from infra import workflow_process_registry
from agent.video import VideoAdapter
from agent.wan import WanAdapter


class NoRedirectSharedTests(unittest.TestCase):
    def test_unmocked_requests_are_stopped_by_network_guards(self):
        import socket
        from contract.platform_tools import RequestsJsonOpener
        with mock.patch('socket.getaddrinfo', side_effect=AssertionError('unexpected real DNS')), \
                mock.patch('socket.socket.connect', side_effect=AssertionError('unexpected real network')):
            with mock.patch.dict('os.environ', {'DRAMA_SUPPRESS_NETWORK': '0', 'NO_PROXY': '*'}):
                with self.assertRaisesRegex(AssertionError, 'unexpected real DNS'):
                    RequestsJsonOpener().open(urllib.request.Request('https://provider.invalid'), timeout=0.1)
                with socket.socket() as connection:
                    with self.assertRaisesRegex(AssertionError, 'unexpected real network'):
                        connection.connect(('127.0.0.1', 443))

    def test_every_adapter_uses_the_one_implementation(self):
        # 仍走 urllib 的适配器共享唯一拒跳实现；TTS 走统一有界二进制出口。
        for module in (local_video,):
            self.assertIs(module.no_redirect, api_endpoints.no_redirect, module.__name__)
        for status in (301, 302, 303, 307, 308):
            for adapter in ('local_video', 'seedream', 'tts'):
                with self.subTest(adapter=adapter, status=status):
                    self.refuse_redirect(adapter, status)

    def refuse_redirect(self, adapter, status):
        seen, responses = [], []
        base = 'http://127.0.0.1:18189' if adapter == 'local_video' else 'https://provider.invalid'
        path = '/prompt' if adapter == 'local_video' else '/images/generations' if adapter == 'seedream' else '/audio/speech'
        url = base + path

        def respond_requests(sender, prepared, **settings):
            self.assertEqual(prepared.url, url, 'redirect target must never be sent')
            seen.append((prepared.url, prepared.headers, prepared.body))
            response = requests.Response()
            response.status_code, response.url, response.reason = status, url, 'Moved'
            response.request = prepared
            response.headers['Location'] = 'https://elsewhere.invalid/steal'
            response.raw = HTTPResponse(io.BytesIO(b'{}'), preload_content=False)
            responses.append(response)
            return response

        def respond_urllib(handler, request):
            self.assertEqual(request.full_url, url, 'redirect target must never be sent')
            seen.append((request.full_url, dict(request.header_items()), request.data))
            headers = Message()
            headers['Location'] = 'https://elsewhere.invalid/steal'
            response = urllib.response.addinfourl(io.BytesIO(b'{}'), headers, url, status)
            response.msg = 'Moved'
            responses.append(response)
            return response

        with mock.patch('socket.getaddrinfo', side_effect=AssertionError('unexpected real DNS')), \
                mock.patch('socket.socket.connect', side_effect=AssertionError('unexpected real network')), \
                mock.patch.object(requests.adapters.HTTPAdapter, 'send', respond_requests), \
                mock.patch.object(urllib.request.HTTPHandler, 'http_open', respond_urllib), \
                mock.patch.object(urllib.request.HTTPSHandler, 'https_open', respond_urllib), \
                mock.patch('urllib.request.getproxies', dict):
            try:
                with mock.patch.dict('os.environ', {'DRAMA_SUPPRESS_NETWORK': '0', 'NO_PROXY': '*'}):
                    if adapter == 'local_video':
                        with self.assertRaises(urllib.error.HTTPError) as caught:
                            local_video.LocalAPI(base).call(path, {'prompt': 'synthetic'})
                        self.assertEqual(caught.exception.code, status)
                    elif adapter == 'seedream':
                        with self.assertRaises(seedream_api.Uncertain):
                            seedream_api.request_image({'base_url': base, 'api_key': 'SYNTHETIC'},
                                                       {'prompt': 'synthetic'})
                    else:
                        settings = {'base_url': base, 'model': 'synthetic', 'voice': 'synthetic'}
                        from infra import http_client
                        request_bytes = http_client.request_bytes
                        with mock.patch.object(http_client, 'request_bytes', wraps=request_bytes) as send_bytes, \
                                mock.patch.object(tts_api, 'load_key', return_value='SYNTHETIC'):
                            with self.assertRaisesRegex(ValueError, f'HTTP {status}'):
                                tts_api.synthesize('测试', settings=settings)
                            send_bytes.assert_called_once()
                            self.assertEqual(send_bytes.call_args.kwargs['timeout'], 120)
                            self.assertEqual(send_bytes.call_args.kwargs['max_bytes'], 64 * 1024 * 1024)
            finally:
                for response in responses:
                    response.close()
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0][2], 'original request body must reach the send seam')
        if adapter != 'local_video':
            self.assertEqual({name.lower(): value for name, value in seen[0][1].items()}['authorization'],
                             'Bearer SYNTHETIC')
        self.assertTrue(all(response.raw.closed if isinstance(response, requests.Response) else response.closed
                            for response in responses))

    def test_redirects_are_refused(self):
        handler = api_endpoints.no_redirect()
        self.assertIsInstance(handler, HTTPRedirectHandler)
        self.assertIsNone(handler.redirect_request(None, None, 302, 'Found', {}, 'http://elsewhere/'))


class RunRegisteredSharedTests(unittest.TestCase):
    def test_engine_run_delegates_and_unregisters(self):
        done = workflow_engines._run([sys.executable, '-c', 'import sys;sys.exit(3)'], '.', '', subprocess.DEVNULL,
                                     subprocess.DEVNULL, 30)
        self.assertEqual(done, 3)
        self.assertEqual(workflow_process_registry.processes('.'), [])

    def test_timeout_kills_and_names_the_caller(self):
        with self.assertRaises(ValueError) as caught:
            workflow_process_registry.run_registered(
                [sys.executable, '-c', 'import time;time.sleep(30)'], '.', '',
                (subprocess.DEVNULL, subprocess.DEVNULL), 0.3, timeout_label='某引擎运行超时')
        self.assertIn('某引擎运行超时', str(caught.exception))
        self.assertEqual(workflow_process_registry.processes('.'), [])


class WanAdapterContractTests(unittest.TestCase):
    def test_wan_adapter_is_a_video_adapter(self):
        self.assertTrue(issubclass(WanAdapter, VideoAdapter))


if __name__ == '__main__':
    unittest.main()
