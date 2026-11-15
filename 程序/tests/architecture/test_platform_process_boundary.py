"""P2：可见本地程序必须经平台启动边界，后台进程只能出现在受控模块。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import module_scan_files, parse


_BACKGROUND_BOUNDARIES = frozenset({
    'asset_thumbs', 'codex_tasks', 'storage_maintenance',
    'log_maintenance',
})


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else None
    return None


class PlatformProcessBoundaryTests(unittest.TestCase):
    def test_direct_popen_is_limited_to_platform_or_background_boundaries(self):
        offenders = []
        for path in module_scan_files():
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.Call) and _dotted_name(node.func) == 'subprocess.Popen':
                    if path.stem not in _BACKGROUND_BOUNDARIES | {'platform_tools'}:
                        offenders.append(f'{path.name}:{node.lineno}')
        self.assertEqual(
            offenders, [],
            '可见本地程序请改用 platform_tools.launch_windows_app()：\n' + '\n'.join(offenders),
        )

    def test_taskkill_is_limited_to_native_or_platform_adapters(self):
        offenders = []
        for path in module_scan_files():
            for node in ast.walk(parse(path)):
                if not isinstance(node, ast.Call) or _dotted_name(node.func) != 'subprocess.run':
                    continue
                if not node.args or not isinstance(node.args[0], (ast.List, ast.Tuple)) or not node.args[0].elts:
                    continue
                first = node.args[0].elts[0]
                if isinstance(first, ast.Constant) and first.value == 'taskkill' and path.stem not in {'platform_tools', 'native_apps'}:
                    offenders.append(f'{path.name}:{node.lineno}')
        self.assertEqual(offenders, [], 'taskkill 请收敛到平台或本地应用适配器：\n' + '\n'.join(offenders))
