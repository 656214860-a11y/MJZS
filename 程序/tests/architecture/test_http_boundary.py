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


if __name__ == '__main__':
    unittest.main()
