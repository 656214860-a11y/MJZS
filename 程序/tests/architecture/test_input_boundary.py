"""已迁移的表单不得退回页面内手拼文本输入视觉。"""
from __future__ import annotations

import ast
import unittest
from tests.architecture._scan import ROOT, parse


EXCLUDED_PARTS = {"tests", "tasks_round", "维护记录", ".git", "__pycache__", "voice_asr_venv"}


class InputBoundaryTests(unittest.TestCase):

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
