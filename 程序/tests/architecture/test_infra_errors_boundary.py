# -*- coding: utf-8 -*-
"""L1-H7／I6-2：L1 内置异常中文文案 raise 棘轮守卫。

口径：L1 模块中 ``raise ValueError/RuntimeError/OSError/Exception(``
且异常表达式含 CJK 字符串的 raise 处数，按模块登记基线，只许减少
不许新增。存量迁移到 ``contract.infra_errors``（I7 起）后计数应下降；
新模块出现违规、或存量模块超基线即红。更宽口径（任意异常类型的
CJK raise）由 ``test_layer_relations`` LR-07 兜底。
"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._layers import LAYERS
from tests.architecture._scan import ROOT, module_scan_files, module_name, parse

# I6 轮实测基线（R3407 登记）：模块 → 内置异常中文 raise 处数。
# 只许下调；模块迁移完应从表中删除或归零。
BUILTIN_CJK_RAISE_BASELINE = {
    'account_store': 1,
    'api_endpoints': 6,
    'app_icon': 1,
    'asset_prompt_rules': 1,
    'broadcaster': 3,
    'client_profiles': 2,
    'cloud_assets': 8,
    'comfy_runtime': 3,
    'continuity_ledger': 7,
    'core': 14,
    'diagnostic_capture': 2,
    'engine_probe': 1,
    'file_cache': 1,
    'file_index': 7,
    'global_library_service': 6,
    'integrations': 1,
    'line_endings': 3,
    'media': 5,
    'model_pool': 7,
    'model_router': 1,
    'model_secrets': 9,
    'native_apps': 3,
    'native_asset_codec': 4,
    'pet_state': 2,
    'project_settings': 1,
    'publication': 7,
    'qwen_setup': 2,
    'script_text_reader': 5,
    'seedream_api': 9,
    'stage_model_value': 2,
    'storage_maintenance': 45,
    'ui_plugin_registry': 1,
    'workflow_process_registry': 3,
    'workspace_maintenance': 1,
}

# 任务书 I6-2 点名口径：这四个内置异常类型。
BUILTIN_TYPES = frozenset({'ValueError', 'RuntimeError', 'OSError', 'Exception'})

_STDLIB = frozenset({'__future__', 're', 'os', 'sys', 'json', 'ast', 'enum',
                     'dataclasses', 'typing', 'pathlib', 'collections'})


def _has_cjk(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                and any('一' <= ch <= '鿿' for ch in sub.value)):
            return True
    return False


def _raise_func_name(exc: ast.AST) -> str:
    target = exc.func if isinstance(exc, ast.Call) else exc
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ''


def measured_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in module_scan_files():
        name = module_name(path)
        if LAYERS.get(name) != 1:
            continue
        try:
            tree = parse(path)
        except Exception:
            continue
        n = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            if _raise_func_name(node.exc) not in BUILTIN_TYPES:
                continue
            if _has_cjk(node.exc):
                n += 1
        if n:
            counts[name] = n
    return counts


class InfraErrorsBoundaryTests(unittest.TestCase):
    def test_builtin_cjk_raises_within_baseline(self):
        measured = measured_counts()
        regressions = []
        for name, count in sorted(measured.items()):
            baseline = BUILTIN_CJK_RAISE_BASELINE.get(name, 0)
            if count > baseline:
                regressions.append('%s：实测 %d > 基线 %d' % (name, count, baseline))
        self.assertEqual(regressions, [],
                         'L1 内置异常中文 raise 新增违规（应改抛 contract.infra_errors）：\n'
                         + '\n'.join(regressions))

    def test_baseline_modules_registered(self):
        measured = measured_counts()
        unregistered = {n: c for n, c in measured.items()
                        if n not in BUILTIN_CJK_RAISE_BASELINE}
        self.assertEqual(unregistered, {},
                         '出现未登记的 L1 内置异常中文 raise 模块：%s' % unregistered)

    def test_infra_errors_module_is_l0_contract_pure(self):
        # contract/infra_errors.py 只允许 import contract.* 与标准库（L0 纯契约）。
        path = ROOT / 'contract' / 'infra_errors.py'
        tree = parse(path)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if not (node.module == 'contract' or node.module.startswith('contract.')
                        or node.module.split('.')[0] in _STDLIB):
                    bad.append(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] not in _STDLIB:
                        bad.append(alias.name)
        self.assertEqual(bad, [], 'infra_errors 引入非契约依赖：%s' % bad)


if __name__ == '__main__':
    unittest.main()
