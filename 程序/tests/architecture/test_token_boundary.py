"""UI 路线图 v1 §一 第 2 项：设计 token 内联视觉常量棘轮（只减不增）。

R1388 只读审计口径（269 个生产 `.py`）：业务页内联 hex 111 处/8 文件、数字 `padx/pady` 213 处/19 文件。
本门禁按文件冻结这两个类别的当前计数——**只许减少、不许增加，也不许新增文件**；
把内联常量迁移为 `ui_tokens` 取值后，可直接下调或删除对应基线，无需改断言。

未纳入棘轮（只审计、另议）：数字 `font/wraplength/width/height` 候选 189 处/32 文件——`width/height`
部分属布局而非纯视觉常量，待后续轮次逐处裁定；数字圆角/字号等由 review 逐轮查（规则 34）。
"""
from __future__ import annotations

import ast
import re
import unittest

from tests.architecture._scan import ROOT, parse


# 与 test_dialog_boundary / test_button_boundary 一致：测试、轮次记录与维护记录不参与生产门禁。
EXCLUDED_PARTS = {"tests", "tasks_round", "维护记录", ".git", "__pycache__", "skills"}
# 权威与豁免：token／主题／组件基类／图标调色自身即定义视觉常量的地方。
AUTHORITY_FILES = {"ui_tokens.py", "ui_theme.py", "ui_widgets.py", "ui_icons.py"}

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_PADDING_ARGS = frozenset({"padx", "pady", "ipadx", "ipady"})

# R1389 冻结基线（R1388 审计口径，键＝相对 程序/ 的 posix 路径）。
HEX_BASELINE = {
    "app.py": 2, "asset_detail.py": 21, "cell_hover.py": 6, "desktop.py": 31,
    "keyframe_comfy.py": 3, "pet_ui.py": 45, "previs_monitor.py": 1,
    "storyboard_table_ui.py": 2,
}
PADDING_BASELINE = {
    "agent/prompt_optimizer.py": 16, "app.py": 7, "asset_detail.py": 21,
    "asset_reference_images.py": 18, "asset_reference_import.py": 7,
    "background_characters.py": 3, "cell_hover.py": 4, "cloud_assets.py": 5,
    "desktop.py": 40, "keyframe_comfy.py": 36, "native_assets.py": 9,
    "prompt_window.py": 3, "qwen_setup.py": 9, "seedream_settings.py": 9,
    "shared_video_controls.py": 1, "skill_panel.py": 1, "storyboard_selection.py": 1,
    "white_model.py": 12, "workflow_settings.py": 11,
}


def _production_files():
    """递归生产模块，排除测试／轮次记录／维护记录／skills 独立脚本与权威定义文件。"""
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in AUTHORITY_FILES:
            continue
        yield path, relative.as_posix()


def hex_color_count(tree):
    """字符串常量里出现的 `#rrggbb` 颜色字面量数量。"""
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and isinstance(node.value, str)
               and _HEX.search(node.value))


def numeric_padding_count(tree):
    """`padx/pady/ipadx/ipady` 取数字字面量的次数。"""
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if (keyword.arg in _PADDING_ARGS
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, (int, float))):
                    total += 1
    return total


class TokenBoundaryTests(unittest.TestCase):
    def _assert_ratchet(self, baseline, counter, label):
        actual = {}
        for path, key in _production_files():
            count = counter(parse(path))
            if count:
                actual[key] = count
        violations = {key: value for key, value in actual.items()
                      if value > baseline.get(key, 0)}
        self.assertEqual(violations, {},
                         f'{label} 只许减少、不许增加（新增文件亦违规，须改用 token）：'
                         + str(violations))

    def test_inline_hex_colors_do_not_increase(self):
        self._assert_ratchet(HEX_BASELINE, hex_color_count, '内联颜色 hex')

    def test_numeric_padding_does_not_increase(self):
        self._assert_ratchet(PADDING_BASELINE, numeric_padding_count, '数字 padx/pady')

    def test_authority_files_are_exempt(self):
        keys = {key for _, key in _production_files()}
        for name in sorted(AUTHORITY_FILES):
            self.assertNotIn(name, keys)

    def test_hex_predicate_canary(self):
        self.assertEqual(hex_color_count(ast.parse('w.configure(bg="#123456")')), 1)
        self.assertEqual(hex_color_count(ast.parse('w.configure(bg=COLORS["bg"])')), 0)

    def test_padding_predicate_canary(self):
        self.assertEqual(numeric_padding_count(ast.parse('f.pack(padx=8)')), 1)
        self.assertEqual(numeric_padding_count(ast.parse('f.pack(padx=SPACING.sm)')), 0)
