"""弹窗入口棘轮：历史裸窗可逐批减少，业务页不得新增。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


# 首批迁移后的历史基线；数值只能下降。新增裸 Toplevel 必须先建立统一组件迁移任务。
LEGACY_RAW_TOPLEVEL_MAX = {
    'app.py': 3, 'asset_batch.py': 1, 'asset_detail.py': 1,
    'asset_reference_images.py': 2, 'asset_reference_import.py': 1,
    'background_characters.py': 1, 'cloud_assets.py': 1, 'cloud_video.py': 1,
    'desktop.py': 4, 'keyframe_comfy.py': 1, 'local_previs.py': 1,
    'local_video.py': 1, 'pet_cloud.py': 1, 'pet_models_ui.py': 1,
    'pet_settings_ui.py': 1, 'prompt_window.py': 1, 'qwen_setup.py': 1,
    'reference_wall.py': 1, 'seedream_settings.py': 1, 'skill_panel.py': 5,
    'stage_exec.py': 1, 'stage_models.py': 1, 'tts_settings.py': 1,
    'white_model.py': 2, 'workflow_settings.py': 1,
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
