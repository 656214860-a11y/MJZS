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

    def test_main_workbench_direct_inputs_do_not_increase(self):
        tree = parse(ROOT / "app.py")
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
        self.assertLessEqual(len(_direct_inputs(app)), LEGACY_DIRECT_INPUT_MAX['app.py'],
                             "主工作台历史直构输入数量只能下降")

    def test_desktop_direct_inputs_do_not_increase(self):
        tree = parse(ROOT / "desktop.py")
        self.assertLessEqual(len(_direct_inputs(tree)), LEGACY_DIRECT_INPUT_MAX['desktop.py'],
                             "桌面页历史直构输入数量只能下降")

    def test_business_ui_has_no_direct_entry_or_text_construction(self):
        actual = {}
        for filename, maximum in LEGACY_DIRECT_INPUT_MAX.items():
            count = len(_direct_inputs(parse(ROOT / filename)))
            if count > maximum:
                actual[filename] = f'{count}>{maximum}'
        self.assertEqual(actual, {}, "业务 UI 历史直构输入数量只能下降：" + str(actual))
LEGACY_DIRECT_INPUT_MAX = {
    'app.py': 6, 'asset_detail.py': 1, 'asset_reference_import.py': 1,
    'cloud_assets.py': 1, 'cloud_video.py': 1, 'desktop.py': 5,
    'keyframe_comfy.py': 2, 'local_previs.py': 1, 'prompt_window.py': 1,
    'qwen_setup.py': 1, 'seedream_settings.py': 1, 'skill_panel.py': 2,
    'storyboard_files.py': 1, 'tts_settings.py': 3, 'white_model.py': 1,
    'workflow_settings.py': 2, 'agent/prompt_optimizer.py': 1,
}

def _direct_inputs(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr in {'Entry', 'Text'}
            and isinstance(node.func.value, ast.Name) and node.func.value.id in {'tk', 'ttk'}]
