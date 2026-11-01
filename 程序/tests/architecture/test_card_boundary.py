"""已迁移的信息承载区必须继续使用统一 Card。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse, parse_desktop


class CardBoundaryTests(unittest.TestCase):
    def test_cloud_video_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("cloud_video.py", "_CloudSettingsWindow")  # settings_window 改写成类

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

    def test_background_character_dialog_uses_card_for_its_content(self):
        self._assert_settings_card("background_characters.py", "show")

    def test_reference_wall_uses_card_for_its_content(self):
        self._assert_settings_card("reference_wall.py", "_ReferenceWall")  # R1828 show 改写成类

    def test_qwen_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("qwen_setup.py")

    def test_tts_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("tts_settings.py")

    def test_seedream_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("seedream_settings.py")

    def test_prompt_optimizer_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("agent/prompt_optimizer.py", "settings")

    def test_workflow_settings_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("workflow_settings_dialog.py", "show_settings")

    def test_pet_settings_hub_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("pet_settings_ui.py", "open_hub")

    def test_pet_model_windows_use_card_for_their_configuration_group(self):
        self._assert_settings_card("pet_models_ui.py", "window")

    def test_white_model_picker_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("white_model.py", "choose_previs")

    def test_white_model_workspace_uses_card_for_its_configuration_group(self):
        self._assert_settings_card("white_model.py", "open_previs")

    def test_asset_detail_page_blocks_use_card(self):
        """资产详情页的六个信息／操作单元（正典板、锚点、职责、变体、原始数据、待确认）统一用 Card。"""
        tree = parse(ROOT / "asset_detail.py")
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "Card"]
        self.assertGreaterEqual(len(calls), 7, "资产详情页的信息块必须使用统一 Card")

    def test_native_assets_and_asset_batch_forms_use_card(self):
        """原生资产窗与批量资产表单的配置区统一用 Card（标题行改为卡内标签）。"""
        for filename in ("native_assets.py", "asset_batch.py"):
            tree = parse(ROOT / filename)
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == "Card"]
            self.assertTrue(calls, f"{filename} 的配置承载区必须使用统一 Card")

    def test_keyframe_comfy_windows_use_card(self):
        """首帧 ComfyUI 窗的两个配置单元（生成模型与接口、ComfyUI 连接与模型接口）统一用 Card。"""
        tree = parse(ROOT / "keyframe_comfy.py")
        # R1841：show 改写成类，Card 调用位于窗口类内
        calls = [node for cls in tree.body if isinstance(cls, ast.ClassDef)
                 and cls.name.startswith("_KeyframeComfy")
                 for node in ast.walk(cls) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "Card"]
        self.assertGreaterEqual(len(calls), 2, "首帧 ComfyUI 窗的配置单元必须使用统一 Card")

    def test_desktop_pages_use_card_for_content_groups(self):
        """桌面页的分类导航、连续性与视频主页信息承载区统一用 Card（标题行改为卡内标签）。"""
        tree = parse_desktop()  # R1505：桌面页构建分布在 desktop.py 与迁出的 Mixin 模块
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "Card"]
        self.assertGreaterEqual(len(calls), 6, "桌面页的信息块必须使用统一 Card")

    def _assert_settings_card(self, filename, function_name="show"):
        tree = parse(ROOT / filename)
        imported = {
            alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            and node.module == "ui_widgets" for alias in node.names
        }
        self.assertIn("Card", imported)
        function = next(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                        and node.name == function_name)
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "Card"]
        self.assertEqual(len(calls), 1)
