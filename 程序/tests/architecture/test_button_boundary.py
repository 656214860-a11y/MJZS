"""已迁移表单不得退回裸 tk/ttk.Button（含静态导入与赋值别名）。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


def raw_button_calls(tree):
    """解析静态名称链；不声称覆盖 getattr、动态导入或跨函数数据流。"""
    names = {}
    nodes = list(ast.walk(tree))
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split('.')[0]] = (
                    alias.name if alias.asname else alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                names[alias.asname or alias.name] = node.module + '.' + alias.name

    def resolve(node):
        if isinstance(node, ast.Name):
            return names.get(node.id, '')
        if isinstance(node, ast.Attribute):
            base = resolve(node.value)
            return base + '.' + node.attr if base else ''
        return ''

    # 支持 Button = tk.Button、widgets = ttk 及其有限静态别名链。
    for _ in range(len(nodes)):
        changed = False
        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = resolve(node.value)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and value and target.id not in names:
                        names[target.id] = value
                        changed = True
        if not changed:
            break
    return [node for node in nodes if isinstance(node, ast.Call)
            and resolve(node.func) in {'tkinter.Button', 'tkinter.ttk.Button'}]


class ButtonBoundaryTests(unittest.TestCase):
    def _assert_semantic_buttons(self, filename, required=('PrimaryButton', 'SecondaryButton')):
        tree = parse(ROOT / filename)
        raw = [node.lineno for node in raw_button_calls(tree)]
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                   and node.module == 'ui_widgets' for alias in node.names}
        self.assertEqual(raw, [], f'{filename} 不得使用裸 tk/ttk.Button；违规行号')
        for component in required:
            self.assertIn(component, imports)

    def test_asset_reference_import_uses_semantic_buttons(self):
        self._assert_semantic_buttons('asset_reference_import.py')

    def test_background_character_dialog_uses_semantic_buttons(self):
        self._assert_semantic_buttons('background_characters.py')

    def test_asset_reference_windows_use_semantic_buttons(self):
        self._assert_semantic_buttons('asset_reference_images.py')

    def test_cloud_asset_settings_use_semantic_buttons(self):
        self._assert_semantic_buttons('cloud_assets.py')

    def test_qwen_settings_use_semantic_buttons(self):
        self._assert_semantic_buttons('qwen_setup.py')

    def test_prompt_optimizer_settings_use_semantic_buttons(self):
        self._assert_semantic_buttons('agent/prompt_optimizer.py')

    def test_seedream_settings_use_semantic_buttons(self):
        self._assert_semantic_buttons('seedream_settings.py')

    def test_workflow_settings_use_semantic_buttons(self):
        self._assert_semantic_buttons('workflow_settings.py')

    def test_shared_video_controls_use_semantic_buttons(self):
        self._assert_semantic_buttons('shared_video_controls.py', required=('SecondaryButton',))

    def test_prompt_window_uses_semantic_buttons(self):
        self._assert_semantic_buttons('prompt_window.py', required=('PrimaryButton',))

    def test_reference_wall_uses_semantic_buttons(self):
        self._assert_semantic_buttons('reference_wall.py')

    def test_white_model_uses_semantic_buttons(self):
        self._assert_semantic_buttons('white_model.py')

    def test_keyframe_comfy_uses_semantic_buttons(self):
        self._assert_semantic_buttons('keyframe_comfy.py')

    def test_native_assets_uses_semantic_buttons(self):
        self._assert_semantic_buttons('native_assets.py')

    def test_skill_panel_uses_semantic_buttons(self):
        self._assert_semantic_buttons('skill_panel.py')

    def test_asset_detail_uses_semantic_buttons(self):
        self._assert_semantic_buttons('asset_detail.py')

    def test_app_uses_semantic_buttons(self):
        self._assert_semantic_buttons('app.py')

    def test_desktop_uses_semantic_buttons(self):
        self._assert_semantic_buttons('desktop.py')

    def test_video_navigation_uses_semantic_buttons(self):
        self._assert_semantic_buttons('video_navigation.py', required=('SecondaryButton',))

    def test_tk_import_alias_canaries_are_detected(self):
        for source in (
            'import tkinter\ntkinter.Button(root)',
            'import tkinter as widgets\nwidgets.Button(root)',
            'from tkinter import Button\nButton(root)',
            'from tkinter import Button as B\nB(root)',
        ):
            with self.subTest(source=source):
                self.assertEqual(len(raw_button_calls(ast.parse(source))), 1)

    def test_ttk_import_alias_canaries_are_detected(self):
        for source in (
            'from tkinter import ttk\nttk.Button(root)',
            'from tkinter import ttk as themed\nthemed.Button(root)',
            'import tkinter.ttk\ntkinter.ttk.Button(root)',
            'import tkinter.ttk as themed\nthemed.Button(root)',
            'from tkinter.ttk import Button as B\nB(root)',
        ):
            with self.subTest(source=source):
                self.assertEqual(len(raw_button_calls(ast.parse(source))), 1)

    def test_assignment_alias_canaries_are_detected(self):
        for source in (
            'import tkinter as tk\nB = tk.Button\nB(root)',
            'from tkinter import ttk\nwidgets = ttk\nB = widgets.Button\nB(root)',
            'from tkinter.ttk import Button\nB: object = Button\nB(root)',
        ):
            with self.subTest(source=source):
                self.assertEqual(len(raw_button_calls(ast.parse(source))), 1)

    def test_semantic_and_unrelated_buttons_are_not_flagged(self):
        tree = ast.parse('from ui_widgets import PrimaryButton as B, SecondaryButton\n'
                         'from another_library import Button\n'
                         'B(root)\nSecondaryButton(root)\nButton(root)\n')
        self.assertEqual(raw_button_calls(tree), [])
