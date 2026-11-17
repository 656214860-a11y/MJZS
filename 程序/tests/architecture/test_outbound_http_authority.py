"""出站 HTTP 唯一入口：生产代码只在 platform_tools 里直接建连，其余一律走 open_https（AGENTS §2.3 第 42 条）。

白名单是棘轮，只许减少：新增的直接 ``urlopen``／``HTTPConnection``／``create_connection``／requests 出站即红。
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


def requests_calls(tree):
    """跟踪 requests 导入及 Session 绑定，不按通用方法名猜测出站。"""
    methods = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'request', 'send'}
    session_types = {'requests.Session', 'requests.sessions.Session', 'requests.session'}
    owners = {'requests', 'requests.api', 'requests.Session',
              'requests.sessions.Session', 'requests.Session()'}

    class Scanner(ast.NodeVisitor):
        def __init__(self):
            self.bindings = {}
            self.hits = []

        def origin(self, node):
            if isinstance(node, ast.Name):
                return self.bindings.get(node.id, '')
            if isinstance(node, ast.Attribute):
                owner = self.origin(node.value)
                return owner + '.' + node.attr if owner else ''
            if isinstance(node, ast.Call) and self.origin(node.func) in session_types:
                return 'requests.Session()'
            return ''

        def bind(self, target, origin):
            if isinstance(target, ast.Name):
                self.bindings[target.id] = origin

        def visit_Import(self, node):
            for alias in node.names:
                self.bindings[alias.asname or alias.name.split('.')[0]] = (
                    alias.name if alias.asname else alias.name.split('.')[0])

        def visit_ImportFrom(self, node):
            for alias in node.names:
                self.bindings[alias.asname or alias.name] = (
                    (node.module or '') + '.' + alias.name if not node.level else '')

        def visit_Call(self, node):
            owner, _, method = self.origin(node.func).rpartition('.')
            if owner in owners and method in methods:
                self.hits.append((method, node.lineno))
            self.generic_visit(node)

        def visit_Assign(self, node):
            self.visit(node.value)
            origin = self.origin(node.value)
            for target in node.targets:
                self.bind(target, origin)

        def visit_AnnAssign(self, node):
            if node.value is not None:
                self.visit(node.value)
                self.bind(node.target, self.origin(node.value))

        def visit_With(self, node):
            for item in node.items:
                self.visit(item.context_expr)
                self.bind(item.optional_vars, self.origin(item.context_expr))
            for statement in node.body:
                self.visit(statement)

        visit_AsyncWith = visit_With

        def visit_FunctionDef(self, node):
            for expression in [*node.decorator_list, *node.args.defaults,
                               *filter(None, node.args.kw_defaults)]:
                self.visit(expression)
            outer = self.bindings.copy()
            self.bindings[node.name] = ''
            for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                        node.args.vararg, node.args.kwarg]:
                if arg is not None:
                    self.bindings[arg.arg] = ''
            for statement in node.body:
                self.visit(statement)
            self.bindings = outer
            self.bindings[node.name] = ''

        visit_AsyncFunctionDef = visit_FunctionDef

    scanner = Scanner()
    scanner.visit(tree)
    return scanner.hits


class OutboundHttpAuthorityTests(unittest.TestCase):
    def test_only_the_host_adapter_opens_connections_directly(self):
        offenders = {}
        for path in production_runtime_files():
            tree = parse(path)
            hits = raw_calls(tree) + requests_calls(tree)
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

    def test_requests_scanner_flags_direct_outbound_samples(self):
        samples = [
            ('import requests\nrequests.get("https://x")', 'get'),
            ('import requests\nrequests.post("https://x")', 'post'),
            ('import requests\nrequests.request("GET", "https://x")', 'request'),
            ('import requests as rq\nrq.get("https://x")', 'get'),
            ('from requests import get as fetch\nfetch("https://x")', 'get'),
            ('from requests import request as fetch\nfetch("GET", "https://x")', 'request'),
            ('import requests\nrequests.Session.request(session, "GET", "https://x")', 'request'),
            ('import requests\nrequests.Session.send(session, prepared)', 'send'),
            ('import requests\nsession = requests.Session()\nsession.get("https://x")', 'get'),
            ('import requests as rq\nsession = rq.Session()\nsession.request("GET", "https://x")', 'request'),
            ('from requests import Session as Client\nsession = Client()\nsession.send(prepared)', 'send'),
            ('import requests\nrequests.Session().post("https://x")', 'post'),
            ('import requests as rq\nwith rq.Session() as session:\n    session.get("https://x")', 'get'),
        ]
        for source, method in samples:
            with self.subTest(source=source):
                tree = ast.parse(source)
                self.assertEqual(requests_calls(tree), [(method, len(source.splitlines()))])

    def test_requests_scanner_passes_host_api_and_unrelated_business_objects(self):
        samples = [
            'import platform_tools\nplatform_tools.open_https("https://x", timeout=5)',
            'business.request("job")\nbusiness.send("event")\nbusiness.get("key")',
            'from business import request as fetch\nfetch("job")',
            'import requests\nrequests.Request("GET", "https://x")\nrequests.Session()',
            'import requests\nsession = business.Session()\nsession.request("job")\nsession.send("event")',
            'import requests as rq\nrq = business\nrq.get("key")',
            'import requests\nsession = requests.Session()\nsession = business\nsession.send("event")',
            'import requests\ndef run(requests):\n    requests.request("job")',
            'from requests import get as fetch\ndef run(fetch):\n    fetch("job")',
        ]
        for source in samples:
            with self.subTest(source=source):
                self.assertEqual(requests_calls(ast.parse(source)), [])


if __name__ == '__main__':
    unittest.main()
