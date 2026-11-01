"""platform_tools.open_https 照常跟随重定向，但跳到另一来源时不把凭据头转给跳转目标。

只替换贴着网络的 http_open／https_open，跳转走 urllib 真实的那套机制（同
test_model_pool_redirects），每一跳实际发出的请求都记下来对照。
"""
import io
import ssl
import unittest
from email.message import Message
from unittest.mock import patch
import urllib.request
import urllib.response

import platform_tools

START = 'https://account.invalid/v1/me'
CREDENTIALS = {'Authorization': 'Bearer SYNTHETIC', 'Cookie': 'session=SYNTHETIC',
               'Proxy-Authorization': 'Basic SYNTHETIC'}
PLAIN = {'Accept': 'application/json', 'X-Client-Version': 'synthetic'}


class OpenHttpsRedirectTests(unittest.TestCase):
    def follow(self, location, *, status=302, data=None, context=None):
        """START 回 status 跳到 location，下一跳回 200；返回实际发出的每一个请求。"""
        sent = []

        def respond(handler, request):
            sent.append(request)
            headers = Message()
            code = 200
            if len(sent) == 1:
                code = status
                headers['Location'] = location
            response = urllib.response.addinfourl(io.BytesIO(b'{}'), headers, request.full_url, code)
            response.msg = 'Synthetic response'
            self.addCleanup(response.close)
            return response

        with patch.object(urllib.request.HTTPHandler, 'http_open', respond), \
                patch.object(urllib.request.HTTPSHandler, 'https_open', respond):
            with platform_tools.open_https(START, headers=dict(CREDENTIALS, **PLAIN), data=data,
                                           context=context) as response:
                self.assertEqual(response.read(), b'{}')
        self.assertEqual(len(sent), 2, '跳转照常跟随')
        return sent

    def assert_credentials_dropped(self, request):
        self.assertIsNone(request.get_header('Authorization'))
        self.assertIsNone(request.get_header('Cookie'))
        # 系统代理配了口令时 ProxyHandler 会补它自己的 Proxy-Authorization，这里只认调用方给的那份没转过去。
        self.assertNotEqual(request.get_header('Proxy-authorization'), 'Basic SYNTHETIC')
        self.assertEqual(request.get_header('Accept'), 'application/json')
        self.assertEqual(request.get_header('X-client-version'), 'synthetic')

    def test_a_hop_to_another_origin_drops_the_credentials(self):
        for context in (None, ssl.create_default_context()):
            for location in ('https://collector.invalid/v1/me',          # 换主机
                             'http://account.invalid/v1/me',             # https→http 降级
                             'https://account.invalid:8443/v1/me',       # 换端口
                             'https://evil.account.invalid/v1/me',       # 子域也是另一来源
                             'https://account.invalid@collector.invalid/',  # 用户名位置伪装主机
                             'https://account.invalid:99999/v1/me'):     # 端口写坏，按另一来源处理
                for status in (301, 302, 303, 307, 308):
                    with self.subTest(context=context is not None, location=location, status=status):
                        first, second = self.follow(location, status=status, context=context)
                        self.assertEqual(first.get_header('Authorization'), 'Bearer SYNTHETIC')
                        self.assertEqual(first.get_header('Cookie'), 'session=SYNTHETIC')
                        self.assert_credentials_dropped(second)

    def test_a_hop_within_the_same_origin_keeps_the_credentials(self):
        for context in (None, ssl.create_default_context()):
            for location in ('https://account.invalid/v1/other',
                             '/v1/other',                                # 相对地址
                             'https://ACCOUNT.invalid:443/v1/other'):    # 主机大小写与显式默认端口
                with self.subTest(context=context is not None, location=location):
                    _, second = self.follow(location, context=context)
                    self.assertTrue(second.full_url.endswith('/v1/other'), second.full_url)
                    self.assertEqual(second.get_header('Authorization'), 'Bearer SYNTHETIC')
                    self.assertEqual(second.get_header('Cookie'), 'session=SYNTHETIC')
                    self.assertEqual(second.get_header('Accept'), 'application/json')

    def test_a_post_redirected_elsewhere_becomes_a_bare_get(self):
        first, second = self.follow('https://collector.invalid/v1/me', status=303, data=b'{"a": 1}')
        self.assertEqual(first.get_method(), 'POST')
        self.assertEqual(second.get_method(), 'GET')
        self.assertIsNone(second.data)
        self.assert_credentials_dropped(second)


if __name__ == '__main__':
    unittest.main()
