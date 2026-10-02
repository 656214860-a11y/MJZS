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

    def test_main_workbench_uses_unified_inputs_not_direct_entry_or_text(self):
        tree = parse(ROOT / "app.py")
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
        direct = [node for node in ast.walk(app) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute)
                  and node.func.attr in {"Entry", "Text"}
                  and isinstance(node.func.value, ast.Name)
                  and node.func.value.id in {"tk", "ttk"}]
        self.assertEqual(direct, [], "主工作台不得退回业务层直接构造 Entry/Text")

    def test_desktop_pages_use_text_area_not_direct_tk_text(self):
        tree = parse(ROOT / "desktop.py")
        direct = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute)
                  and isinstance(node.func.value, ast.Name)
                  and node.func.value.id == "tk" and node.func.attr == "Text"]
        self.assertEqual(direct, [], "桌面页面不得退回业务层直接构造 tk.Text")

    def test_business_ui_has_no_direct_entry_or_text_construction(self):
        offenders = []
        for path in ROOT.rglob("*.py"):
            if "tests" in path.parts or path.name == "ui_widgets.py":
                continue
            tree = parse(path)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in {"Entry", "Text"}
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in {"tk", "ttk"}):
                    offenders.append(str(path.relative_to(ROOT)))
                    break
        self.assertEqual(offenders, [], "业务 UI 必须使用 LineInput/TextArea：" + ", ".join(offenders))
