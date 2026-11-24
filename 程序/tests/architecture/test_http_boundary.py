"""HTTP 边界门禁：直接 urlopen／build_opener 只允许在 http_client 与存量白名单；
写死的外部地址必须登记在 ``docs/process/外部依赖清单.md``（与直连白名单同属一张边界表）。

白名单随 T3 迁移逐轮只减不增；新增文件命中即红。
"""
from __future__ import annotations

import ast
import re
import unittest

from tests.architecture._scan import ROOT, parse, production_runtime_files

ALLOWED = frozenset({
    'infra/http_client.py',
    # 存量直连点，按 T3 迁移计划逐个迁入 http_client 后移除
    'local_video.py',
    'contract/platform_tools.py',
})

ENDPOINT_DOC = 'docs/process/外部依赖清单.md'
_ADDR = re.compile(r'^https?://\S+')
_LOC = re.compile(r'([\w\-./]+\.py):(\d+)')


def _rel(path) -> str:
    parts = path.parts
    idx = parts.index('程序') if '程序' in parts else len(parts) - 1
    return '/'.join(parts[idx + 1:])


def _http_calls(path) -> list[int]:
    lines = []
    for node in ast.walk(parse(path)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else '')
        if name in ('urlopen', 'build_opener'):
            lines.append(node.lineno)
    return lines


def _doc_entries() -> set:
    path = ROOT / ENDPOINT_DOC
    if not path.is_file():
        return set()
    return {(loc, int(line)) for loc, line in _LOC.findall(path.read_text(encoding='utf-8'))}


def _docstring_ranges(tree: ast.Module) -> list:
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                ranges.append((first.value.lineno, first.value.end_lineno or first.value.lineno))
    return ranges


def _hardcoded_addresses() -> list:
    found = []
    for path in production_runtime_files():
        rel = path.relative_to(ROOT).as_posix()
        tree = parse(path)
        strings = _docstring_ranges(tree)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and _ADDR.match(node.value)
                    and not any(start <= node.lineno <= end for start, end in strings)):
                found.append((rel, node.lineno, node.value))
    return found


OUTBOUND_DOC = 'docs/process/外发内容清单.md'

# 出站点口径：对这些传输入口名的 Load 引用（直接调用、注入绑定、基类继承都算
# 外发点）；``webbrowser.open``（含 ``*.webbrowser.open``）单独按链尾匹配。
_OUTBOUND_NAMES = frozenset({
    'open_https', 'open_websocket', 'open_target',
    'request_json', 'request_bytes',
    'http_transport', '_http_transport', 'http_stream',
    'tools_search', 'tools_fetch',
    'urlopen', 'urlretrieve', 'build_opener',
    'RequestsJsonOpener', 'LocalComfyClient', 'Comfy',
    'create_connection', 'WebSocket', 'send_text',
    'probe_http_endpoint', 'tcp_listener', 'snapshot_download',
})


def _dotted(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _dotted(node.value)
        return owner + '.' + node.attr if owner else node.attr
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == '__import__' and node.args
            and isinstance(node.args[0], ast.Constant)):
        return str(node.args[0].value)
    return ''


def _outbound_points(path) -> set:
    """生产文件里的外发点行号集合。"""
    hits = set()
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            if node.attr in _OUTBOUND_NAMES:
                hits.add(node.lineno)
            elif node.attr == 'open' and _dotted(node.value).endswith('webbrowser'):
                hits.add(node.lineno)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in _OUTBOUND_NAMES:
            hits.add(node.lineno)
    return hits


class HttpBoundaryTests(unittest.TestCase):
    def test_direct_http_calls_stay_inside_allowlist(self):
        offenders = []
        for path in production_runtime_files():
            rel = _rel(path)
            if rel in ALLOWED:
                continue
            hits = _http_calls(path)
            if hits:
                offenders.append(f'{rel}:{hits[0]}')
        self.assertEqual(offenders, [],
                         '新增直接 HTTP 调用须迁入 http_client：' + '; '.join(offenders))

    def test_allowlist_has_no_stale_entries(self):
        present = {rel for path in production_runtime_files()
                   if _http_calls(path) for rel in [_rel(path)]}
        stale = sorted((ALLOWED - {'infra/http_client.py'}) - present)
        self.assertEqual(stale, [], '白名单条目已无直连调用，请移除：' + '; '.join(stale))

    def test_hardcoded_addresses_are_registered(self):
        """清单：生产代码新增写死的外部地址而 ``docs/process/外部依赖清单.md`` 未登记就红。"""
        registered = _doc_entries()
        found = _hardcoded_addresses()
        unregistered = [(rel, line, url) for rel, line, url in found if (rel, line) not in registered]
        self.assertEqual([], [(f'{rel}:{line}', url) for rel, line, url in unregistered],
                         '未登记的外部地址（登记在 %s）：' % ENDPOINT_DOC
                         + '；'.join('%s %s' % (f'{rel}:{line}', url) for rel, line, url in unregistered))


class OutboundRegistryTests(unittest.TestCase):
    """REL-11：外发内容清单必须登记每一个出站点，且条目与代码一一对应。"""

    def _registry(self) -> str:
        path = ROOT / OUTBOUND_DOC
        self.assertTrue(path.is_file(), '缺少外发内容清单：' + OUTBOUND_DOC)
        return path.read_text(encoding='utf-8')

    def test_outbound_registry_lists_required_flows(self):
        text = self._registry()
        for flow in ('联网采风', '模型请求', '更新检查', '账号服务'):
            self.assertIn(flow, text, '外发内容清单未列出流程：' + flow)

    def test_outbound_registry_covers_every_outbound_point(self):
        registered = {(loc, int(line)) for loc, line in _LOC.findall(self._registry())}
        unregistered = {}
        for path in production_runtime_files():
            rel = _rel(path)
            missing = sorted(_outbound_points(path)
                             - {line for loc, line in registered if loc == rel})
            if missing:
                unregistered[rel] = missing
        self.assertEqual(unregistered, {},
                         '未登记的外发点（写入 %s）：' % OUTBOUND_DOC + repr(unregistered))

    def test_outbound_registry_has_no_stale_entries(self):
        detected = set()
        for path in production_runtime_files():
            rel = _rel(path)
            detected.update((rel, line) for line in _outbound_points(path))
        stale = sorted({(loc, int(line)) for loc, line in _LOC.findall(self._registry())}
                       - detected)
        self.assertEqual(stale, [], '外发内容清单登记了已不存在的出站点：' + repr(stale))


if __name__ == '__main__':
    unittest.main()
