"""L4 延迟导入只能通过 UI 插件登记表。"""
from __future__ import annotations

import ast
import unittest

import ui_plugin_registry
from tests.architecture._layers import LAYERS
from tests.architecture._scan import ROOT, module_name, parse


_L4_MODULES = frozenset({
    'desktop', 'app', 'pet_ui', 'pet_cloud', 'pet_settings_ui', 'pet_models_ui',
    'responsive_ui', 'ui_theme', 'cell_hover', 'prompt_window', 'asset_detail',
    'skill_panel', 'storyboard_files', 'storyboard_table_ui', 'storyboard_previs_ui', 'asset_batch',
})
_DYNAMIC_IMPORTS = frozenset({'__import__', 'import_module', 'importlib.import_module'})


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else None
    return None


class DynamicImportRegistryTests(unittest.TestCase):
    def test_l4_dynamic_imports_use_the_plugin_registry(self) -> None:
        """登记的 L4 页面不得直接调用动态 import。"""
        offenders = []
        for name in sorted(_L4_MODULES):
            path = ROOT / f'{name}.py'
            if not path.is_file():
                continue
            # 本轮列表是审计指定的 L4 扫描范围；LAYERS 仅用于保留
            # 当前登记信息，不能因登记滞后而跳过实际页面的动态导入扫描。
            _registered_layer = LAYERS.get(module_name(path))
            tree = parse(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _dotted_name(node.func) in _DYNAMIC_IMPORTS:
                    offenders.append(f'{path.name}:{node.lineno} {_dotted_name(node.func)}')
        self.assertEqual(
            offenders, [],
            'L4 动态导入必须改用 ui_plugin_registry.module():\n' + '\n'.join(offenders),
        )

    def test_registry_rejects_unknown_plugin(self):
        with self.assertRaisesRegex(ValueError, '未登记'):
            ui_plugin_registry.module('unregistered_plugin')

    def test_registry_has_the_ui_plugins_used_by_callers(self):
        expected = {'skill_panel', 'stage_flow', 'pet_ui', 'agent.prompt_optimizer',
                    'workflow_settings'}
        self.assertTrue(expected <= ui_plugin_registry.UI_PLUGINS)
