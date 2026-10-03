"""已迁移表单的按钮必须经语义组件，不能退回裸 ttk.Button。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class ButtonBoundaryTests(unittest.TestCase):
    def test_asset_reference_import_uses_semantic_buttons(self):
        tree = parse(ROOT / 'asset_reference_import.py')
        raw = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Attribute)
               and isinstance(node.func.value, ast.Name)
               and node.func.value.id == 'ttk' and node.func.attr == 'Button']
        names = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertEqual(raw, [], '资产参考图导入窗不得使用裸 ttk.Button')
        self.assertIn('PrimaryButton', names)
        self.assertIn('SecondaryButton', names)
