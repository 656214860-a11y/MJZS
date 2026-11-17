# -*- coding: utf-8 -*-
"""DeepSeek Search／Fetch 工具接口自检：参数校验、状态分类、重试判定与请求体。

REQ-S01-41：采风的检索与抓取只经这两个接口，鉴权沿用模型池的 DEEPSEEK_API_KEY。
运行：python tests/test_model_pool_tools.py
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import infra.model_pool as model_pool

HEADERS = {'Authorization': 'Bearer test', 'Content-Type': 'application/json'}


def capture(result):
    """假传输：记下每次请求，回同一个结果。"""
    calls = []

    def transport(url, payload, headers, timeout):
        calls.append({'url': url, 'payload': payload, 'headers': headers, 'timeout': timeout})
        return result

    return transport, calls


class ValidationTests(unittest.TestCase):
    """请求发出前的形状校验：不合规的直接拒，不浪费一次计费请求。"""

    def test_query_shape_is_enforced_before_any_request(self):
        """query 必须 1～128 字符且不能全为空白。"""
        transport, calls = capture({'ok': True, 'status': 200, 'data': {'results': []}})
        for query in ('', '   ', '\n\t', 'x' * 129):
            result = model_pool.tools_search(query, transport=transport, headers=HEADERS)
            self.assertFalse(result['ok'], repr(query)[:20])
            self.assertEqual(result['kind'], 'invalid')
            self.assertEqual(result['status'], 400)
        self.assertEqual(calls, [], '非法参数不该发出请求')
        ok = model_pool.tools_search('x' * 128, transport=transport, headers=HEADERS)
        self.assertTrue(ok['ok'])
        self.assertEqual(len(calls), 1)

    def test_fetch_url_must_be_http_with_host_and_no_credentials(self):
        """url 只认含 host 的 http(s)，且不带用户名密码。"""
        transport, calls = capture({'ok': True, 'status': 200, 'data': {'content': 'x'}})
        for url in ('', 'ftp://example.com/a', 'example.com/a',
                    'https://user:pw@example.com/a', 'https://' + 'a' * 8192):
            result = model_pool.tools_fetch(url, transport=transport, headers=HEADERS)
            self.assertEqual(result['kind'], 'invalid', url[:32])
        self.assertEqual(calls, [])
        self.assertTrue(model_pool.tools_fetch('https://example.com/a', transport=transport,
                                               headers=HEADERS)['ok'])

    def test_count_is_clamped_into_the_documented_range(self):
        """count 夹到 1～50；need_content 与 ori_question 原样进请求体。"""
        transport, calls = capture({'ok': True, 'status': 200, 'data': {'results': []}})
        model_pool.tools_search('某剧', count=99, transport=transport, headers=HEADERS)
        model_pool.tools_search('某剧', count=0, transport=transport, headers=HEADERS)
        model_pool.tools_search('某剧', count='乱写', need_content=True,
                                ori_question='问' * 200, transport=transport, headers=HEADERS)
        self.assertEqual([item['payload']['count'] for item in calls], [50, 1, 10])
        self.assertIs(calls[2]['payload']['need_content'], True)
        self.assertEqual(len(calls[2]['payload']['ori_question']), 128)
        self.assertTrue(all(item['url'].endswith('/v1/tools/search') for item in calls))


class StatusTests(unittest.TestCase):
    """HTTP 状态 → 重试策略：只有 408／429／5xx 值得等一等。"""

    def test_status_table(self):
        expected = {401: ('auth', False), 402: ('balance', False), 403: ('blocked', False),
                    404: ('empty', False), 408: ('client', True), 429: ('rate', True),
                    500: ('server', True), 502: ('server', True), 504: ('server', True)}
        for status, (kind, retry) in expected.items():
            self.assertEqual(model_pool.tools_error_kind(status), kind, status)
            self.assertEqual(model_pool.tools_retryable(status), retry, status)
        self.assertTrue(model_pool.tools_retryable(0), '本地网络异常按可重试处理')

    def test_failure_keeps_the_status_and_kind(self):
        transport, _calls = capture({'ok': False, 'status': 404, 'error': 'HTTP 404：没有正文'})
        result = model_pool.tools_fetch('https://example.com/js', transport=transport, headers=HEADERS)
        self.assertFalse(result['ok'])
        self.assertEqual((result['status'], result['kind']), (404, 'empty'))
        self.assertIn('404', result['error'])

    def test_missing_key_is_reported_as_auth_instead_of_raising(self):
        """缺钥匙要变成一条可提示的失败，不是把采风整条链崩掉。"""
        transport, calls = capture({'ok': True, 'status': 200, 'data': {'results': []}})
        with mock.patch.object(model_pool, 'credential',
                               side_effect=ValueError('当前接口缺少有效 API Key')):
            result = model_pool.tools_search('某剧', transport=transport)
        self.assertEqual((result['ok'], result['kind'], result['status']), (False, 'auth', 0))
        self.assertEqual(calls, [], '没有钥匙就不该发请求')


class TransportTests(unittest.TestCase):
    """成功路径：结果原样带回，密钥不出现在返回值里。"""

    def test_results_and_content_are_returned_verbatim(self):
        rows = [{'title': 'A', 'url': 'https://example.com/a', 'authority': 3,
                 'rerank_score': 2.4, 'snippet': 's', 'summary': 'm', 'content': '',
                 'date': '2026-06-01T00:00:00+00:00', 'site_name': '站点',
                 'site_icon': None}]
        transport, _calls = capture({'ok': True, 'status': 200,
                                     'data': {'results': rows, 'extra': 'x'}})
        result = model_pool.tools_search('某剧', transport=transport, headers=HEADERS)
        self.assertEqual(result['results'], rows)
        self.assertNotIn('extra', result, '只把文档字段带出来，不透传整个响应')
        page = model_pool.tools_fetch('https://example.com/a', transport=transport, headers=HEADERS)
        self.assertEqual(page['content'], '')
        self.assertEqual(page['title'], '')

    def test_base_url_falls_back_to_the_builtin_host(self):
        """模型池没有 DeepSeek 记录时退回出厂地址，不因配置缺失而拼出空 URL。"""
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(model_pool.tools_base(td), model_pool.TOOLS_BASE_URL)

    def test_headers_carry_the_key_only_in_the_authorization_field(self):
        with mock.patch.object(model_pool, 'credential', return_value='sk-test'):
            headers = model_pool.tools_headers()
        self.assertEqual(headers['Authorization'], 'Bearer sk-test')
        self.assertEqual(sorted(headers), ['Authorization', 'Content-Type'])


if __name__ == '__main__':
    unittest.main()
