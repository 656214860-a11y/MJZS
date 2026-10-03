"""已迁移的表单不得退回页面内手拼文本输入视觉。"""
from __future__ import annotations

import ast
import unittest
from tests.architecture._scan import ROOT, parse


EXCLUDED_PARTS = {"tests", "tasks_round", "维护记录", ".git", "__pycache__"}


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

    def test_main_workbench_has_no_direct_inputs(self):
        tree = parse(ROOT / "app.py")
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
        self.assertEqual(_direct_inputs(app), [], "主工作台输入必须走 LineInput/TextArea")

    def test_desktop_has_no_direct_inputs(self):
        tree = parse(ROOT / "desktop.py")
        self.assertEqual(_direct_inputs(tree), [], "桌面页输入必须走 LineInput/TextArea")

    def test_business_ui_has_no_direct_entry_or_text_construction(self):
        actual = {}
        for path in ROOT.rglob('*.py'):
            if (path.name == 'ui_widgets.py'
                    or any(part in EXCLUDED_PARTS for part in path.parts)):
                continue
            count = len(_direct_inputs(parse(path)))
            if count:
                actual[path.relative_to(ROOT).as_posix()] = count
        self.assertEqual(actual, {}, "业务 UI 不得绕过 LineInput/TextArea：" + str(actual))
def _direct_inputs(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr in {'Entry', 'Text'}
            and isinstance(node.func.value, ast.Name) and node.func.value.id in {'tk', 'ttk'}]
