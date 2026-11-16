"""HTTP 边界门禁：直接 urlopen／build_opener 只允许在 http_client 与存量白名单。

白名单随 T3 迁移逐轮只减不增；新增文件命中即红。
"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import parse, production_runtime_files

ALLOWED = frozenset({
    'infra/http_client.py',
    # 存量直连点，按 T3 迁移计划逐个迁入 http_client 后移除
    'api_endpoints.py',
    'batch_frames_tool/batch_frames.py',
    'local_video.py',
    'contract/platform_tools.py',
    'seedream_api.py',
    'domain/tts_api.py',
})


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


if __name__ == '__main__':
    unittest.main()
