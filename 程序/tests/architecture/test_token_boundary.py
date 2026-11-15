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

from tests.architecture._scan import ROOT, parse, registry_key


# 与 test_dialog_boundary / test_button_boundary 一致：测试、轮次记录与维护记录不参与生产门禁。
EXCLUDED_PARTS = {"tests", "tasks_round", "维护记录", ".git", "__pycache__", "skills"}
# 权威与豁免：token／主题／组件基类／图标调色自身即定义视觉常量的地方。
AUTHORITY_FILES = {"ui_tokens.py", "ui_theme.py", "ui_widgets.py", "ui_splash.py", "ui_tooltip.py", "ui_icons.py"}  # 后二者自 ui_widgets 拆出

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_PADDING_ARGS = frozenset({"padx", "pady", "ipadx", "ipady"})
_LAYOUT_ARGS = frozenset({"width", "height", "wraplength"})
_LAYOUT_ALLOWED = (0, 1)  # 0／1 是“自动／最小”的哨兵值，不算魔法数字

# R1389 冻结基线（R1388 审计口径，键＝相对 程序/ 的 posix 路径）。
# R1428 统一调色板：主题与业务页迁移到 ui_tokens.COLORS；剩余为宠物插画色与监视页 HTML 样式。
HEX_BASELINE = {
    # R1868：pet_ui／pet_ui_support 已清零；previs_monitor 余 1 处为导出 HTML 报告的 CSS（非 Tk）
    "previs_monitor.py": 1,
}
PADDING_BASELINE = {
    # R1868：剩余数字间距全部就近迁到 SPACING（等距取小档）；0 改 SPACING['none']
}

# R1777 新增：控件 width／height／wraplength 的数字字面量（不含 0、1）。按文件冻结当前值，
# 只许下降；迁移到 ui_tokens 的命名常量后同步下调。像素级布局数字要逐处裁定，所以不强制清零。
LAYOUT_NUMBER_BASELINE = {
    # R1885：业务页数字 width/height/wraplength 已迁到 CHAR_WIDTH／TEXT_ROWS／WRAPLENGTH／SPACING 刻度。
    # 剩余登记豁免——画布插画描边宽度（宠物形象几何，不是控件布局）与 ComfyUI 生成分辨率（请求参数）。
    "comfy_service.py": 2, "pet_ui_support.py": 13, "pet_ui_view.py": 1,
}


def _production_files():
    """递归生产模块，排除测试／轮次记录／维护记录／skills 独立脚本与权威定义文件。"""
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in AUTHORITY_FILES:
            continue
        yield path, registry_key(path)


def hex_color_count(tree):
    """字符串常量里出现的 `#rrggbb` 颜色字面量数量。"""
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and isinstance(node.value, str)
               and _HEX.search(node.value))


def numeric_padding_count(tree):
    """`padx/pady/ipadx/ipady` 取数字字面量的次数（含元组元素）。"""
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg not in _PADDING_ARGS:
                    continue
                # R1885：元组形式 `pady=(0, 6)` 的每个数字元素同样计数。
                value = keyword.value
                for item in (value.elts if isinstance(value, ast.Tuple) else [value]):
                    if (isinstance(item, ast.Constant) and isinstance(item.value, (int, float))
                            and not isinstance(item.value, bool)):
                        total += 1
    return total


def numeric_layout_count(tree):
    """`width/height/wraplength` 取数字字面量（不含 0、1）的次数。"""
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                value = keyword.value
                if (keyword.arg in _LAYOUT_ARGS and isinstance(value, ast.Constant)
                        and isinstance(value.value, (int, float)) and not isinstance(value.value, bool)
                        and value.value not in _LAYOUT_ALLOWED):
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

    def test_numeric_layout_values_do_not_increase(self):
        self._assert_ratchet(LAYOUT_NUMBER_BASELINE, numeric_layout_count, '数字 width/height/wraplength')

    def test_layout_predicate_canary(self):
        self.assertEqual(numeric_layout_count(ast.parse('w.configure(width=120, wraplength=300)')), 2)
        self.assertEqual(numeric_layout_count(ast.parse('w.configure(width=0, height=1, width=WIDTH)')), 0)

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
        self.assertEqual(numeric_padding_count(ast.parse('f.pack(pady=(0, 6))')), 2)
        self.assertEqual(numeric_padding_count(ast.parse("f.pack(pady=(SPACING['none'], SPACING['xs']))")), 0)
