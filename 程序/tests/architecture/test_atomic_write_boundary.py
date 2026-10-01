"""正式成果写入必须经统一原子服务或已登记的受控边界。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import module_name, parse, production_files


_DIRECT_WRITE_METHODS = frozenset({"write_text", "write_bytes"})
_ATOMIC_BOUNDARIES = frozenset({"model_secrets", "qwen_adapter", "workflow_engines"})
_TEMPORARY_BOUNDARIES = frozenset({"app_shortcut"})


def _is_direct_write(call: ast.Call) -> bool:
    """识别绕开服务的文件写入调用，不把 read/open 或目录操作误报为写入。"""
    if isinstance(call.func, ast.Attribute) and call.func.attr in _DIRECT_WRITE_METHODS:
        if isinstance(call.func.value, ast.Name) and call.func.value.id == 'line_endings':
            return False
        return True
    if not isinstance(call.func, ast.Name) or call.func.id != "open":
        return False
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            return any(flag in str(keyword.value.value) for flag in "wx")
    return len(call.args) > 1 and isinstance(call.args[1], ast.Constant) and any(
        flag in str(call.args[1].value) for flag in "wx")


def _write_lines(path):
    return tuple(node.lineno for node in ast.walk(parse(path))
                 if isinstance(node, ast.Call) and _is_direct_write(node))


class AtomicWriteBoundaryTests(unittest.TestCase):
    def test_direct_production_writes_are_limited_to_registered_boundaries(self):
        offenders = []
        for path in production_files():
            name = module_name(path)
            lines = _write_lines(path)
            if lines and name not in _ATOMIC_BOUNDARIES | _TEMPORARY_BOUNDARIES:
                offenders.extend('%s:%d' % (path.name, line) for line in lines)
        self.assertEqual(offenders, [], '正式成果请改走 agent.core / line_endings；未登记直接写入：'
                         + ', '.join(offenders))

    def test_registered_atomic_boundaries_prove_temporary_then_replace(self):
        for path in production_files():
            name = module_name(path)
            if name not in _ATOMIC_BOUNDARIES:
                continue
            source = path.read_text(encoding='utf-8')
            with self.subTest(module=name):
                self.assertIn('temporary_path(', source)
                self.assertIn('replace(', source)

    def test_background_adapters_validate_report_body_before_publication(self):
        for name in ('qwen_adapter', 'workflow_engines'):
            path = next(path for path in production_files() if module_name(path) == name)
            source = path.read_text(encoding='utf-8')
            with self.subTest(module=name):
                self.assertIn('未返回制作报告正文', source)
                self.assertLess(source.index('未返回制作报告正文'),
                                source.index('save_text(Path(report)'))

    def test_shortcut_script_is_temporary_and_is_reclaimed(self):
        path = next(path for path in production_files() if module_name(path) == 'app_shortcut')
        source = path.read_text(encoding='utf-8')
        self.assertIn('tempfile.mkstemp(', source)
        self.assertIn('remove_temporary_file(script_path)', source)
