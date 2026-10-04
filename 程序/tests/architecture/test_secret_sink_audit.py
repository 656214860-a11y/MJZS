"""密钥从受控读取到可见／持久化／提示词出口的最小数据流审计。"""
from __future__ import annotations

import ast
import json
import re
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from tests.architecture._scan import parse, production_files

ROOT = Path(__file__).resolve().parents[2]
CANARY = Path(__file__).with_name('_canary') / 'audit27_secret_violation.py'
LEDGER = ROOT / '维护记录' / '架构统一基数.json'
CRITERIA = ROOT / '维护记录' / '覆盖率审计判据_20261001.md'
SOURCE_CALLS = frozenset({
    'model_secrets.load', 'model_pool.credential', 'pet_llm.credential',
    'api_endpoints.configured_key', 'os.getenv', 'os.environ.get',
})
LOG_METHODS = frozenset({'debug', 'info', 'warning', 'error', 'exception', 'critical'})

def dot(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dot(node.value)
        return f'{parent}.{node.attr}' if parent else node.attr
    return None

def names(node):
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}

def is_source_call(node):
    if not isinstance(node, ast.Call) or dot(node.func) not in SOURCE_CALLS:
        return False
    name = dot(node.func)
    if name not in {'os.getenv', 'os.environ.get'}:
        return True
    return bool(node.args and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and any(word in node.args[0].value.upper()
                        for word in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD')))

def sink_kind(node):
    if not isinstance(node, ast.Call):
        return None
    name = dot(node.func) or ''
    tail = name.rsplit('.', 1)[-1]
    if name == 'print' or tail in LOG_METHODS or 'broadcaster' in name:
        return 'log'
    if name in {'json.dump', 'json.dumps'} or ('task' in name and tail.startswith('save')):
        return 'json'
    if 'prompt' in name.lower() or tail in {'ask', 'chat'}:
        return 'prompt'
    return None

def audit(paths=None):
    """返回同一函数内由受控密钥读取流入敏感 sink 的 `file:line:kind`。"""
    hits = set()
    for path in production_files() if paths is None else paths:
        tree = parse(path) if paths is None else ast.parse(path.read_text(encoding='utf-8'))
        for function in (node for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            tainted = set()
            nodes = sorted(ast.walk(function), key=lambda node: (getattr(node, 'lineno', -1),
                                                                  getattr(node, 'col_offset', -1)))
            for node in nodes:
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    value = node.value
                    if value is not None and (is_source_call(value) or names(value) & tainted):
                        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                        tainted.update(name for target in targets for name in names(target))
                kind = sink_kind(node)
                if kind and (names(node) & tainted):
                    hits.add(f'{path.name}:{node.lineno}:{kind}')
    return hits


class SecretSinkAuditTests(unittest.TestCase):
    def audit_snippet(self, source):
        # Parse fake source only: never import it or call a credential provider.
        path = mock.Mock(spec=Path)
        path.name = 'fake_secret_canary.py'
        path.read_text.return_value = textwrap.dedent(source)
        return audit([path])

    def test_canary_hits_each_sink_kind(self):
        kinds = {item.rsplit(':', 1)[-1] for item in audit([CANARY])}
        self.assertEqual(kinds, {'log', 'json', 'prompt'})

    def test_source_and_sink_matrix_canaries(self):
        sources = (
            "model_secrets.load('FAKE_TEST_KEY')",
            "model_pool.credential('FAKE_TEST_KEY')",
            "pet_llm.credential('FAKE_TEST_KEY')",
            "api_endpoints.configured_key('FAKE_TEST_KEY')",
            "os.getenv('FAKE_TEST_SECRET')",
            "os.environ.get('FAKE_TEST_TOKEN')",
        )
        sinks = {'log': 'logger.warning(token)',
                 'json': 'json.dumps({"payload": token})',
                 'prompt': 'client.chat(message=token)'}
        for source in sources:
            for kind, sink in sinks.items():
                with self.subTest(source=source, kind=kind):
                    self.assertEqual(self.audit_snippet(
                        f'def canary():\n    token = {source}\n    {sink}\n'),
                        {f'fake_secret_canary.py:3:{kind}'})

    def test_local_propagation_canaries(self):
        cases = {
            'assignment_alias': ('alias = token', 'print(alias)', 'log'),
            'annotated_alias': ('alias: str = token', 'print(alias)', 'log'),
            'formatted_keyword': ('alias = f"value={token}"',
                                  'logger.error(message=alias)', 'log'),
            'list_container': ('items = [token]', 'print(items[0])', 'log'),
            'dict_container': ('items = {"value": token}',
                               'json.dumps(items)', 'json'),
            'return_sink': ('alias = token',
                            'return client.send_prompt(alias)', 'prompt'),
        }
        for label, (assignment, sink, kind) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(self.audit_snippet(
                    "def canary():\n    token = os.getenv('FAKE_TEST_SECRET')\n"
                    f'    {assignment}\n    {sink}\n'),
                    {f'fake_secret_canary.py:4:{kind}'})

    def test_nonsecret_counterexamples(self):
        cases = {
            'literal': "def safe():\n    print('FAKE_TEST_SECRET')\n",
            'ordinary_environment':
                "def safe():\n    value = os.getenv('FAKE_TEST_URL')\n    print(value)\n",
            'field_name_only':
                "def safe():\n    json.dumps({'token': 'not-a-credential'})\n",
            'parameter_without_known_source':
                'def safe(token):\n    print(token)\n',
            'request_not_sink':
                "def safe():\n    token = os.getenv('FAKE_TEST_SECRET')\n"
                '    transport.request(headers={"Authorization": token})\n',
            'separate_scope':
                "def reader():\n    token = os.getenv('FAKE_TEST_SECRET')\n"
                "def safe():\n    token = 'not-a-credential'\n    print(token)\n",
        }
        for label, source in cases.items():
            with self.subTest(case=label):
                self.assertEqual(self.audit_snippet(source), set())

    def test_production_has_no_secret_sink_flow(self):
        self.assertEqual(audit(), set(), '受控密钥不得流入日志、任务 JSON 或 prompt')

    def test_ledger_and_criteria_match_the_frozen_scan(self):
        ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
        pending = {f"{item['file']}:{item['point']}"
                   for item in ledger['覆盖率审计27']['items']
                   if item['disposition'] == 'pending'}
        actual = audit()
        self.assertEqual(actual, pending, '密钥 sink 审计不得有漏账或死账')
        matched = re.search(r'^\|27 .*?\|.*?\|.*?\|(\d+)(?:（.*?）)?\|$',
                            CRITERIA.read_text(encoding='utf-8'), re.MULTILINE)
        self.assertIsNotNone(matched, '判据文档缺少第 27 项真候选数')
        self.assertEqual(int(matched.group(1)), len(actual), '第 27 项文档与扫描器不一致')
