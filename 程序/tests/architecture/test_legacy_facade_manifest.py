"""历史兼容门面必须可盘点、可归属并可在到期日自动拦截。"""
from __future__ import annotations

import ast
from datetime import date
from types import FunctionType
import unittest

import legacy_compat
from tests.architecture._scan import module_name, parse, module_scan_files


def _is_legacy_compat(module):
    """T10 包化后生产侧写 ``orchestrator.legacy_compat``，扁平名与包路径都算同一门面。"""
    return module == 'legacy_compat' or module.endswith('.legacy_compat')


def _production_callers():
    callers = {}
    for path in module_scan_files():
        tree = parse(path)
        aliases = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and _is_legacy_compat(node.module):
                for name in node.names:
                    callers.setdefault(name.name, set()).add(module_name(path))
            elif isinstance(node, ast.Import):
                aliases.update(name.asname or name.name for name in node.names
                               if _is_legacy_compat(name.name))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id in aliases):
                callers.setdefault(node.attr, set()).add(module_name(path))
    return {name: tuple(sorted(modules)) for name, modules in callers.items()}


class LegacyFacadeManifestTests(unittest.TestCase):
    def test_every_public_compatibility_entry_has_one_owned_manifest_row(self):
        public = {name for name, value in vars(legacy_compat).items()
                  if isinstance(value, FunctionType) and value.__module__ == legacy_compat.__name__}
        self.assertEqual(set(legacy_compat.FACADE_MANIFEST), public)
        for name, row in legacy_compat.FACADE_MANIFEST.items():
            self.assertEqual(row['owner'], 'legacy_compat', name)
            self.assertEqual(row['retire_after'], legacy_compat.RETIRE_AFTER, name)
            self.assertIsInstance(row['callers'], tuple, name)

    def test_manifest_callers_equal_production_references(self):
        actual = _production_callers()
        declared = {name: row['callers'] for name, row in legacy_compat.FACADE_MANIFEST.items()}
        self.assertEqual(actual, {name: callers for name, callers in declared.items() if callers},
                         '新增历史兼容调用必须登记唯一门面所有者与调用方')

    def test_facade_is_not_past_its_retirement_date(self):
        today = date.today()
        for name, row in legacy_compat.FACADE_MANIFEST.items():
            deadline = date.fromisoformat(row['retire_after'])
            self.assertGreater(deadline, today,
                               '%s 已到淘汰日；须在 P3-2 删除或迁移该 facade' % name)


if __name__ == '__main__':
    unittest.main()
