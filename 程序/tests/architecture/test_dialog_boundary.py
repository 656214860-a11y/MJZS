"""弹窗入口棘轮：历史裸窗可逐批减少，业务页不得新增。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


def _raw_toplevel_calls(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == 'Toplevel']


class DialogBoundaryTests(unittest.TestCase):
    def test_dialogs_use_the_unified_boundary(self):
        actual = {}
        for path in ROOT.glob('*.py'):
            if path.name in {'ui_widgets.py', 'ui_theme.py', 'run_selftests.py'}:
                continue
            count = len(_raw_toplevel_calls(parse(path)))
            if count:
                actual[path.name] = count
        self.assertEqual(actual, {},
                         '业务层弹窗必须经 BaseDialog/FormDialog/ConfirmDialog：'
                         + str(actual))
        tree = parse(ROOT / 'desktop.py')
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'open_brief_creation_form')
        names = [node.func.id for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('FormDialog', names)
        self.assertEqual(_raw_toplevel_calls(method), [])

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
