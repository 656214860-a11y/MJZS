"""已迁移的信息承载区必须继续使用统一 Card。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class CardBoundaryTests(unittest.TestCase):
    def test_qwen_settings_uses_card_for_its_configuration_group(self):
        tree = parse(ROOT / "qwen_setup.py")
        imported = {
            alias.name for node in tree.body if isinstance(node, ast.ImportFrom)
            and node.module == "ui_widgets" for alias in node.names
        }
        self.assertIn("Card", imported)
        show = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "show")
        calls = [node for node in ast.walk(show) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "Card"]
        self.assertEqual(len(calls), 1)
