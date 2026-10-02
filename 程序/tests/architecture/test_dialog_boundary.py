"""弹窗入口棘轮：历史裸窗可逐批减少，业务页不得新增。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


# 首批迁移后的历史基线；数值只能下降。新增裸 Toplevel 必须先建立统一组件迁移任务。
LEGACY_RAW_TOPLEVEL_MAX = {
    'app.py': 0, 'asset_batch.py': 0, 'asset_detail.py': 0,
    'asset_reference_images.py': 0, 'asset_reference_import.py': 0,
    'background_characters.py': 0, 'cloud_assets.py': 0, 'cloud_video.py': 0,
    'desktop.py': 0, 'keyframe_comfy.py': 0, 'local_previs.py': 0,
    'local_video.py': 0, 'pet_cloud.py': 0, 'pet_models_ui.py': 0,
    'pet_settings_ui.py': 0, 'prompt_window.py': 0, 'qwen_setup.py': 0,
    'reference_wall.py': 0, 'seedream_settings.py': 0, 'skill_panel.py': 0,
    'stage_exec.py': 0, 'stage_models.py': 0, 'tts_settings.py': 0,
    'white_model.py': 0, 'workflow_settings.py': 0,
}


def _raw_toplevel_calls(tree):
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == 'Toplevel']


class DialogBoundaryTests(unittest.TestCase):
    def test_dialogs_use_the_unified_boundary(self):
        actual = {}
        for filename, maximum in LEGACY_RAW_TOPLEVEL_MAX.items():
            count = len(_raw_toplevel_calls(parse(ROOT / filename)))
            if count > maximum:
                actual[filename] = f'{count}>{maximum}'
        self.assertEqual(actual, {}, '业务页不得新增裸 Toplevel 对话框：' + str(actual))
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
