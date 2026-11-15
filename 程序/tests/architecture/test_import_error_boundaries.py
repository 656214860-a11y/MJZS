"""ImportError 只能出现在已分类的兼容、平台或核验边界。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import module_name, module_scan_files, parse


_ALLOWED = frozenset({
    'legacy_compat',          # 旧布局只读兼容，带明确淘汰日期。
    'platform_tools',         # winreg 仅在 Windows 可用。
    'hash_backend',           # 解释器内建哈希后端能力探测。
    'stage_completion_service',  # 成果读取失败必须阻断完成事件。
})


def _catches_import_error(handler: ast.ExceptHandler) -> bool:
    def names(node):
        if isinstance(node, ast.Name):
            return {node.id}
        if isinstance(node, ast.Tuple):
            return {item.id for item in node.elts if isinstance(item, ast.Name)}
        return set()
    return 'ImportError' in names(handler.type) or 'ModuleNotFoundError' in names(handler.type)


class ImportErrorBoundaryTests(unittest.TestCase):
    def test_import_error_handlers_have_a_single_registered_boundary(self):
        found = {}
        for path in module_scan_files():
            lines = tuple(node.lineno for node in ast.walk(parse(path))
                          if isinstance(node, ast.ExceptHandler) and _catches_import_error(node))
            if lines:
                found[module_name(path)] = lines
        self.assertEqual(set(found), _ALLOWED,
                         '未经分类的 ImportError 容错必须迁入 facade/平台/核验边界：%r' % found)

    def test_legacy_facade_declares_a_retirement_date(self):
        path = next(path for path in module_scan_files() if module_name(path) == 'legacy_compat')
        self.assertIn("RETIRE_AFTER = '2027-03-31'", path.read_text(encoding='utf-8'))

    def test_non_compatibility_boundaries_keep_their_failure_semantics(self):
        source = {module_name(path): path.read_text(encoding='utf-8') for path in module_scan_files()}
        self.assertIn("if os.name != 'nt'", source['platform_tools'])
        self.assertIn('sys.builtin_module_names', source['hash_backend'])
        self.assertIn("return False, '成果校验失败", source['stage_completion_service'])

