# -*- coding: utf-8 -*-
"""回环预览页暴露面的守护用例（阶段4 T13 裁决＝接受，前提是边界不变）。

裁决背景见 说明/联调测试出口基线.md §5／§6：本地单用户桌面应用，接受 previs_monitor 的
无鉴权回环预览页——能连上 127.0.0.1 的本机主体本来就能直接读同一用户下的项目文件，这一页
只把已经可读的摘要现场重渲染一遍，边际暴露约等于零，为它加令牌只会动到需要真机目视的 GUI 路径。

接受的前提是它的边界不变，本文件钉住这三条：
- 只绑回环（127.0.0.1），不许监听同网其他主机也能访问的地址；
- 只答 GET，其它方法不返回页面；
- 忽略请求路径，只渲染现场生成的那一页，绝不按请求路径读文件（无路径穿越面）。

任何一条被改动都说明裁决前提失效，必须重新裁决，不能默默放宽。
"""
import http.client
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (str(HERE.parent), str(HERE)):
    if folder not in sys.path:
        sys.path.insert(0, folder)

from orchestrator import previs_monitor

PROJECT = 'P监视'
PAGE_MARK = '页哨兵-9f2c'
FILE_MARK = '文件哨兵-1a7b'


class PrevisMonitorExposureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.secret = Path(self.tmp.name) / 'sentinel.txt'
        self.secret.write_text(FILE_MARK, encoding='utf-8')
        logs = Path(self.tmp.name) / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        self.state = {'log_dir': str(logs), 'status': {PROJECT + '|SH001': '已就绪'},
                      'busy': False, 'summary': PAGE_MARK}
        opened = previs_monitor.start(self.state, PROJECT, opener=lambda url: None)
        self.assertIsNotNone(opened, '监视页必须能在本机起得来')
        self.addCleanup(previs_monitor.stop, self.state)
        self.url, self.server = opened
        self.port = self.server.server_address[1]

    def _call(self, method, path, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        self.addCleanup(connection.close)
        connection.request(method, path, body=body)
        response = connection.getresponse()
        payload = response.read().decode('utf-8', 'replace')
        return response.status, response.getheader('Content-Type') or '', payload

    def test_server_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1',
                         '监视页只许绑回环，不得让同网其他主机连上')
        self.assertTrue(self.url.startswith('http://127.0.0.1:'),
                        '给出的地址必须是回环地址：' + self.url)

    def test_get_renders_state_and_ignores_any_request_path(self):
        traversal = '/%2e%2e/%2e%2e/' + self.secret.name
        for path in ('/', '/whatever/else', traversal, '/../' + self.secret.name,
                     '/previs_monitor.py'):
            status, content_type, body = self._call('GET', path)
            self.assertEqual(status, 200, '路径被忽略，固定页一律 200：' + path)
            self.assertIn('text/html', content_type)
            self.assertTrue(body.lstrip().startswith('<!doctype html>'),
                            '回包必须是现场生成的固定页，不是按路径读出来的文件：' + path)
            self.assertIn(PAGE_MARK, body, '固定页必须来自 state：' + path)
            self.assertIn('SH001', body)
            self.assertNotIn(FILE_MARK, body, '绝不能按请求路径读到文件内容：' + path)

    def test_non_get_methods_never_return_the_page(self):
        for method in ('POST', 'PUT', 'DELETE', 'HEAD'):
            with self.subTest(method=method):
                status, _content_type, body = self._call(method, '/', body=b'x' if method == 'POST' else None)
                self.assertNotEqual(status, 200, method + ' 不得返回页面')
                self.assertNotIn(PAGE_MARK, body, method + ' 的响应不得带页面内容')


if __name__ == '__main__':
    unittest.main()