"""已迁移的表单不得退回页面内手拼文本输入视觉。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class InputBoundaryTests(unittest.TestCase):
    def test_brief_creation_form_uses_text_area_not_direct_tk_text(self):
        tree = parse(ROOT / "desktop.py")
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == "open_brief_creation_form")
        direct_texts = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "tk" and node.func.attr == "Text"]
        component_calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                           and isinstance(node.func, ast.Name) and node.func.id == "TextArea"]
        self.assertEqual(direct_texts, [], "首迁表单不得退回业务页直接构造 tk.Text")
        self.assertGreaterEqual(len(component_calls), 2, "紧凑与详情字段均须走 TextArea")
