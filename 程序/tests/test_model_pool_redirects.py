"""Model requests must not forward credentials or payloads through redirects."""
import io
import unittest
from email.message import Message
from unittest.mock import patch
import urllib.request
import urllib.response

import infra.model_pool as model_pool


class ModelRedirectTests(unittest.TestCase):
    def request(self, streaming, status, location=None):
        seen = []

        def respond(handler, request):
            seen.append(request)
            headers = Message()
            if location:
                headers['Location'] = location
            body = (b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                    b'data: [DONE]\n' if streaming else b'{"message":"ok"}')
            response = urllib.response.addinfourl(io.BytesIO(body), headers,
                                                 request.full_url, status)
            response.msg = 'Synthetic response'
            self.addCleanup(response.close)
            return response

        # Replace only socket-facing handlers; exercise the real urllib redirect machinery.
        with patch('urllib.request._opener', None), \
                patch.object(urllib.request.HTTPHandler, 'http_open', respond), \
                patch.object(urllib.request.HTTPSHandler, 'https_open', respond):
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
                        self.assertEqual(seen[0].get_header('Authorization'), 'Bearer SYNTHETIC')
                        self.assertEqual(seen[0].get_header('X-api-key'), 'SYNTHETIC')
                        self.assertEqual(chunks, [])

    def test_requests_carry_a_non_urllib_user_agent(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                _, seen, _ = self.request(streaming, 200)
                agent = seen[0].get_header('User-agent')
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
