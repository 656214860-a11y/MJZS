"""弹窗入口棘轮：历史裸窗可逐批减少，业务页不得新增。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


# 统一基类、主题与全量自检器允许自行构造 Toplevel；其余生产模块一律经
# BaseDialog／FormDialog／ConfirmDialog。
TOPLEVEL_OWNERS = {'ui_widgets.py', 'ui_splash.py', 'ui_tooltip.py', 'ui_theme.py', 'run_selftests.py'}  # ui_splash/ui_tooltip 自 ui_widgets 拆出，职责不变
# 与 test_data_table_boundary 一致：测试、轮次记录与维护记录不参与生产门禁。
EXCLUDED_PARTS = {'tests', 'tasks_round', '维护记录', '.git', '__pycache__'}


def _raw_toplevel_calls(tree):
    """裸构造 Toplevel：``tk.Toplevel(...)``，或 ``from tkinter import Toplevel`` 后的 ``Toplevel(...)``。"""
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == 'Toplevel':
            calls.append(node)
        elif isinstance(func, ast.Name) and func.id == 'Toplevel':
            calls.append(node)
    return calls


class DialogBoundaryTests(unittest.TestCase):
    def test_dialogs_use_the_unified_boundary(self):
        """递归扫描全部生产模块（R922 起应覆盖子目录），不只根目录。"""
        actual = {}
        for path in ROOT.rglob('*.py'):
            relative = path.relative_to(ROOT)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if path.name in TOPLEVEL_OWNERS:
                continue
            count = len(_raw_toplevel_calls(parse(path)))
            if count:
                actual[str(relative)] = count
        self.assertEqual(actual, {},
                         '业务层弹窗必须经 BaseDialog/FormDialog/ConfirmDialog：'
                         + str(actual))
        # R1099 删除创作信息弹窗；全局裸窗门禁继续覆盖全部页面。
        tree = parse(ROOT / 'desktop.py')
        self.assertFalse(any(isinstance(node, ast.FunctionDef) and node.name == 'open_brief_creation_form'
                             for node in ast.walk(tree)))

    def test_raw_toplevel_canary_is_detected(self):
        """镜像：属性式与 ``from tkinter import Toplevel`` 的裸构造都必须被同一谓词识别。"""
        attributed = 'import tkinter as tk\nwin = tk.Toplevel(parent)\n'
        imported = 'from tkinter import Toplevel\nwin = Toplevel(parent)\n'
        self.assertEqual(len(_raw_toplevel_calls(ast.parse(attributed))), 1)
        self.assertEqual(len(_raw_toplevel_calls(ast.parse(imported))), 1)

    def test_prompt_window_uses_base_dialog_not_a_raw_toplevel(self):
        tree = parse(ROOT / 'prompt_window.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'show')
        self.assertEqual(_raw_toplevel_calls(method), [],
                         '提示词窗口不得退回业务层直接构造 tk.Toplevel')
        names = [node.func.id for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('BaseDialog', names)

    def test_qwen_settings_uses_form_dialog_not_a_raw_toplevel(self):
        tree = parse(ROOT / 'qwen_setup.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'show')
        self.assertEqual(_raw_toplevel_calls(method), [],
                         'Qwen 设置不得退回业务层直接构造 tk.Toplevel')
        names = [node.func.id for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('FormDialog', names)

    def test_tts_settings_uses_form_dialog_not_a_raw_toplevel(self):
        tree = parse(ROOT / 'tts_settings.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'show')
        self.assertEqual(_raw_toplevel_calls(method), [],
                         'TTS 设置不得退回业务层直接构造 tk.Toplevel')
        names = [node.func.id for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('FormDialog', names)

    def test_cloud_asset_settings_uses_form_dialog_not_a_raw_toplevel(self):
        tree = parse(ROOT / 'cloud_assets.py')
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'settings')
        self.assertEqual(_raw_toplevel_calls(method), [],
                         '云图片设置不得退回业务层直接构造 tk.Toplevel')
        names = [node.func.id for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('FormDialog', names)
