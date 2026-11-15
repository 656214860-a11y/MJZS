"""出站 HTTP 唯一入口：生产代码只在 platform_tools 里直接建连，其余一律走 open_https（AGENTS §2.3 第 42 条）。

白名单是棘轮，只许减少：新增的直接 ``urlopen``／``HTTPConnection``／``create_connection`` 即红。
"""
from __future__ import annotations

import ast
import textwrap
import unittest

from tests.architecture._scan import ROOT, parse, production_runtime_files

RAW_CALLS = frozenset({'urlopen', 'urlretrieve', 'HTTPConnection', 'HTTPSConnection', 'create_connection'})
ALLOWED = frozenset({'contract/platform_tools.py'})


def raw_calls(tree):
    """返回 ``[(调用名, 行号)]``：直接发起网络连接的调用。"""
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', None)
            if name in RAW_CALLS:
                hits.append((name, node.lineno))
    return hits


class OutboundHttpAuthorityTests(unittest.TestCase):
    def test_only_the_host_adapter_opens_connections_directly(self):
        offenders = {}
        for path in production_runtime_files():
            hits = raw_calls(parse(path))
            if hits and path.relative_to(ROOT).as_posix() not in ALLOWED:
                offenders[path.relative_to(ROOT).as_posix()] = hits
        self.assertEqual(offenders, {}, '出站请求必须走 platform_tools.open_https：' + repr(offenders))

    def test_allowlist_has_no_stale_entries(self):
        for name in ALLOWED:
            self.assertTrue(raw_calls(parse(ROOT / name)), '%s 已不再直接建连，请从白名单删除' % name)

    def test_scanner_flags_known_bad_samples_and_passes_good_ones(self):
        bad = ast.parse(textwrap.dedent('''
            import urllib.request
            urllib.request.urlopen("http://x")
            from urllib.request import urlopen
            urlopen("http://x")
            import http.client
            http.client.HTTPSConnection("x")
        '''))
        self.assertEqual([name for name, _ in raw_calls(bad)], ['urlopen', 'urlopen', 'HTTPSConnection'])
        good = ast.parse('import platform_tools\nplatform_tools.open_https("https://x", timeout=5)\n')
        self.assertEqual(raw_calls(good), [])


if __name__ == '__main__':
    unittest.main()
