"""已迁移的信息承载区必须继续使用统一 Card。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class CardBoundaryTests(unittest.TestCase):
    def test_cloud_video_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("cloud_video.py", "settings_window")

    def test_local_video_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("local_video.py", "settings_window")

    def test_cloud_studio_settings_uses_card_for_its_configuration_group(self):
        tree = parse(ROOT / "app.py")
        imported = {
            alias.name for node in tree.body if isinstance(node, ast.ImportFrom)
            and node.module == "ui_widgets" for alias in node.names
        }
        self.assertIn("Card", imported)
        function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                        and node.name == "settings")
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "Card"]
        self.assertEqual(len(calls), 1)

    def test_asset_reference_import_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("asset_reference_import.py", "show")

    def test_cloud_asset_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("cloud_assets.py", "settings")

    def test_qwen_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("qwen_setup.py")

    def test_tts_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("tts_settings.py")

    def test_seedream_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("seedream_settings.py")

    def test_prompt_optimizer_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("agent/prompt_optimizer.py", "settings")

    def test_workflow_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("workflow_settings.py", "show_settings")

    def test_pet_settings_hub_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("pet_settings_ui.py", "open_hub")

    def test_pet_model_windows_use_card_for_their_configuration_group(self):
        self._assert_settings_card("pet_models_ui.py", "window")

    def test_white_model_picker_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("white_model.py", "choose_previs")

    def test_white_model_workspace_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("white_model.py", "open_previs")

    def _assert_settings_card(self, filename, function_name="show"):
        tree = parse(ROOT / filename)
        imported = {
            alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            and node.module == "ui_widgets" for alias in node.names
        }
        self.assertIn("Card", imported)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == function_name)
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "Card"]
        self.assertEqual(len(calls), 1)
