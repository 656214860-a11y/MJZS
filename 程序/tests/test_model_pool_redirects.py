"""Model requests must not forward credentials or payloads through redirects."""
import io
import os
import unittest
from unittest.mock import patch

import requests
import urllib3

import infra.model_pool as model_pool


def _respond(status, location=None, streaming=False):
    """requests 适配器 send 的替身：出站请求已收敛 RequestsJsonOpener（requests 栈），
    重定向不跟随由 opener 保证，这里只回放状态码与响应体。"""
    body = (b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
            b'data: [DONE]\n' if streaming else b'{"message":"ok"}')
    headers = {'Location': location} if location else {}

    def send(self, request, **kwargs):
        response = requests.Response()
        response.status_code = status
        response.reason = 'Synthetic response'
        response.url = request.url
        response.headers = requests.structures.CaseInsensitiveDict(headers)
        response.raw = urllib3.HTTPResponse(body=io.BytesIO(body),
                                           preload_content=False, decode_content=False)
        response.request = request
        return response

    return send


class ModelRedirectTests(unittest.TestCase):
    def request(self, streaming, status, location=None):
        seen = []

        def send(self, request, **kwargs):
            seen.append(request)
            return _respond(status, location, streaming)(self, request, **kwargs)

        # 只换掉适配器的 send；重定向语义由 RequestsJsonOpener 的真实代码保证。
        with patch.dict(os.environ, {'DRAMA_SUPPRESS_NETWORK': '0', 'NO_PROXY': '*'}), \
                patch('requests.adapters.HTTPAdapter.send', send):
            args = ('https://provider.invalid/v1/chat/completions', {'input': 'synthetic'},
                    {'Authorization': 'Bearer SYNTHETIC', 'x-api-key': 'SYNTHETIC'}, 3)
            chunks = []
            result = (model_pool.http_stream(*args, on_chunk=chunks.append) if streaming
                      else model_pool.http_transport(*args))
        return result, seen, chunks

    def test_redirects_never_send_a_second_request(self):
        for streaming in (False, True):
            for status in (301, 302, 303, 307, 308):
                for target in ('https://other.invalid/collect',
                               'http://provider.invalid/collect',
                               'https://provider.invalid/other'):
                    with self.subTest(streaming=streaming, status=status, target=target):
                        result, seen, chunks = self.request(streaming, status, target)
                        self.assertFalse(result['ok'])
                        self.assertEqual(len(seen), 1)
                        self.assertEqual(seen[0].headers.get('Authorization'), 'Bearer SYNTHETIC')
                        self.assertEqual(seen[0].headers.get('X-api-key'), 'SYNTHETIC')
                        self.assertEqual(chunks, [])

    def test_requests_carry_a_non_urllib_user_agent(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                _, seen, _ = self.request(streaming, 200)
                agent = seen[0].headers.get('User-agent')
                self.assertEqual(agent, model_pool.HTTP_USER_AGENT)
                self.assertNotIn('Python-urllib', agent)

    def test_caller_supplied_user_agent_is_kept(self):
        merged = model_pool._request_headers({'user-agent': 'custom/2', 'Authorization': 'x'})
        self.assertEqual(merged, {'user-agent': 'custom/2', 'Authorization': 'x'})

    def test_successful_responses_are_unchanged(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                result, seen, chunks = self.request(streaming, 200)
                self.assertTrue(result['ok'])
                self.assertEqual(result['status'], 200)
                self.assertEqual(len(seen), 1)
                self.assertEqual(chunks, ['ok'] if streaming else [])


if __name__ == '__main__':
    unittest.main()
