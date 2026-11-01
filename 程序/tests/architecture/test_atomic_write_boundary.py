"""正式成果写入必须经统一原子服务或已登记的受控边界。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, module_name, parse, production_files, production_runtime_files


_DIRECT_WRITE_METHODS = frozenset({"write_text", "write_bytes"})
_ATOMIC_BOUNDARIES = frozenset({"model_secrets", "qwen_adapter", "workflow_engines"})
_TEMPORARY_BOUNDARIES = frozenset({"app_shortcut"})

# R1854：直接 os.replace／Path.replace 会绕过 agent.core.replace 的 Windows 共享冲突重试与发布记录
# （R1853 的 asset_detail_service 就是这样一次“拒绝访问”整次失败）。agent/core.py 是权威实现；
# 其余为登记时的现状（发布日志自身、日志轮转、导入暂存切换、注入的 replace_file 默认值等），只许减少。
_REPLACE_AUTHORITY = "agent/core.py"
_REPLACE_REGISTERED = {
    "agent/core.py": 1,
    "agent/publication.py": 2,
    "image_agent_runner.py": 1,
    "log_maintenance.py": 2,
    "skill_import_service.py": 2,
    "skill_registry.py": 1,
    "stage_execution_service.py": 2,
    "stage_asset_gateways.py": 1,
    "stage_write_preparation_service.py": 3,
    "white_model_service.py": 2,
}


def _is_direct_replace(call: ast.Call) -> bool:
    """os.replace(a, b) 与 Path.replace(target)；str.replace 恒为两个参数，不会误报。"""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr != "replace":
        return False
    if isinstance(func.value, ast.Name) and func.value.id == "os":
        return True
    return len(call.args) == 1 and not call.keywords and not isinstance(func.value, ast.Constant)


def _replace_counts() -> dict:
    counts = {}
    for path in production_runtime_files():
        found = sum(1 for node in ast.walk(parse(path))
                    if isinstance(node, ast.Call) and _is_direct_replace(node))
        if found:
            counts[path.relative_to(ROOT).as_posix()] = found
    return counts


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

    def test_direct_replace_is_limited_to_registered_writers(self):
        counts = _replace_counts()
        bad = []
        for name, actual in sorted(counts.items()):
            allowed = _REPLACE_REGISTERED.get(name, 0)
            if actual > allowed:
                bad.append('%s: %d 处直接 replace > 登记 %d 处' % (name, actual, allowed))
        for name in sorted(set(_REPLACE_REGISTERED) - set(counts) - {_REPLACE_AUTHORITY}):
            bad.append('%s: 已无直接 replace，请从登记表删除' % name)
        self.assertEqual(bad, [], '文件切换请改走 agent.core.replace()／save()：' + '; '.join(bad))

    def test_direct_replace_detector_catches_both_spellings(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            sample = Path(folder) / 'sample.py'
            sample.write_text('import os\nos.replace(a, b)\nPath(a).replace(b)\n'
                              "text.replace('x', 'y')\n", encoding='utf-8')
            calls = [node for node in ast.walk(parse(sample)) if isinstance(node, ast.Call)]
            self.assertEqual(sum(_is_direct_replace(node) for node in calls), 2)

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
