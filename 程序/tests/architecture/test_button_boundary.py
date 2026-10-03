"""已迁移表单的按钮必须经语义组件，不能退回裸 ttk.Button。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class ButtonBoundaryTests(unittest.TestCase):
    def _assert_semantic_buttons(self, filename):
        tree = parse(ROOT / filename)
        raw = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Attribute)
               and isinstance(node.func.value, ast.Name)
               and node.func.value.id == 'ttk' and node.func.attr == 'Button']
        imports = {alias.name for node in tree.body if isinstance(node, ast.ImportFrom)
                   and node.module == 'ui_widgets' for alias in node.names}
        self.assertEqual(raw, [], f'{filename} 不得使用裸 ttk.Button')
        self.assertIn('PrimaryButton', imports)
        self.assertIn('SecondaryButton', imports)

    def test_asset_reference_import_uses_semantic_buttons(self):
        self._assert_semantic_buttons('asset_reference_import.py')

    def test_background_character_dialog_uses_semantic_buttons(self):
        self._assert_semantic_buttons('background_characters.py')

    def test_asset_reference_windows_use_semantic_buttons(self):
        self._assert_semantic_buttons('asset_reference_images.py')
