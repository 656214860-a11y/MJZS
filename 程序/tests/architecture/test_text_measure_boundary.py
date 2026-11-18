"""U1: 文字测宽唯一入口 ``ui_popup.measure_text_width``；存量直接测宽按文件冻结、只减不增。

AST 口径（``production_files_recursive``，不含 tests／tasks_round／维护记录）：

- ``measure_debt``：任何 ``.measure`` 属性访问（``font.measure(...)`` 调用与
  ``m = font.measure`` 绑定方法取法同罪）各计 1——真实字体测宽必须走
  ``ui/ui_popup.py`` 的共享函数，新代码不得自建 ``tkfont.Font`` 再量。
- ``legacy_debt``：``from responsive_ui import measure`` 引入的裸名 ``measure(...)``
  调用——U1 之前的事实测宽入口，存量冻结，新代码一律改走 ``ui_popup``。
- ``approx_debt``：``ord(...)`` 与 ≥0x2E00 整型常量的比较——全角×2／ASCII×1
  字符宽度近似；U1 已清零，基线为空表，出现即红。

``ui/ui_popup.py`` 是共享实现本体（内部 ``face.measure`` 为唯一合法落点），
``ui_popup.py`` 顶层门面不含测宽代码，一并豁免。坏样本由 canary 用例自审。
"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, production_files_recursive

# U1 迁移后三处试点已走共享函数；以下为登记冻结的存量直接测宽，只许减少。
MEASURE_BASELINE = {
    'app.py': 1, 'desktop.py': 1, 'production_lock_fields.py': 1, 'responsive_ui.py': 1,
    'ui/asset_batch.py': 2, 'ui/keyframe_comfy.py': 2, 'ui/pet_models_ui.py': 1,
    'ui/script_line_numbers.py': 1, 'ui/speech_settings_ui.py': 1, 'ui_widgets.py': 4,
}
LEGACY_BASELINE = {'ui/storyboard_table_ui.py': 2}
# 全角×2/ASCII×1 近似在 U1 清零；新代码出现任一处即失败。
APPROX_BASELINE = {}
CJK_BOUNDARY = 0x2E00
EXEMPT = frozenset({'ui/ui_popup.py', 'ui_popup.py'})


def _attr_measure(node):
    return isinstance(node, ast.Attribute) and node.attr == 'measure'


def measure_debt(tree):
    """直接字体测宽处数：``.measure`` 属性访问（调用或绑定方法取法）各计 1。"""
    return sum(1 for node in ast.walk(tree) if _attr_measure(node))


def _legacy_aliases(tree):
    return {a.asname or a.name for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == 'responsive_ui'
            for a in node.names if a.name == 'measure'}


def legacy_debt(tree):
    """``from responsive_ui import measure`` 后的裸名 ``measure(...)`` 调用处数。"""
    aliases = _legacy_aliases(tree)
    if not aliases:
        return 0
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id in aliases)


def _is_ord_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'ord')


def _is_cjk_constant(node):
    return (isinstance(node, ast.Constant) and isinstance(node.value, int)
            and not isinstance(node.value, bool) and node.value >= CJK_BOUNDARY)


def _approx_compare(node):
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return False
    left, right = node.left, node.comparators[0]
    return ((_is_ord_call(left) and _is_cjk_constant(right))
            or (_is_ord_call(right) and _is_cjk_constant(left)))


def approx_debt(tree):
    """全角/半角字符宽度近似处数：``ord(x)`` 与 CJK 边界整型常量的比较。"""
    return sum(1 for node in ast.walk(tree) if _approx_compare(node))


def _overages(counts, baseline):
    return {rel: (count, baseline.get(rel, 0)) for rel, count in counts.items()
            if count > baseline.get(rel, 0)}


def _scan(counter):
    counts = {}
    for path in production_files_recursive():
        relative = path.relative_to(ROOT).as_posix()
        if relative in EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        count = counter(tree)
        if count:
            counts[relative] = count
    return counts


class TextMeasureBoundaryTests(unittest.TestCase):
    def test_direct_measure_debt_only_decreases(self):
        bad = [f'{rel}: {count}>{cap}' for rel, (count, cap) in
               _overages(_scan(measure_debt), MEASURE_BASELINE).items()]
        self.assertEqual(bad, [], '新代码测宽必须走 ui_popup.measure_text_width，不得直接 font.measure')

    def test_legacy_measure_entry_only_decreases(self):
        bad = [f'{rel}: {count}>{cap}' for rel, (count, cap) in
               _overages(_scan(legacy_debt), LEGACY_BASELINE).items()]
        self.assertEqual(bad, [], 'responsive_ui.measure 是冻结旧入口，新代码改走 ui_popup')

    def test_char_width_approximation_is_zero(self):
        bad = [f'{rel}: {count}>{cap}' for rel, (count, cap) in
               _overages(_scan(approx_debt), APPROX_BASELINE).items()]
        self.assertEqual(bad, [], '不得手写全角×2/ASCII×1 字符宽度近似')

    def test_measure_canary(self):
        self.assertEqual(measure_debt(ast.parse("w = font.measure('中')")), 1)
        self.assertEqual(measure_debt(ast.parse("w = tkfont.Font(font='TkDefaultFont').measure('x')")), 1)
        self.assertEqual(measure_debt(ast.parse("m = font.measure\nw = m('x')")), 1)
        self.assertEqual(measure_debt(ast.parse(
            "from ui.ui_popup import measure_text_width\nw = measure_text_width(FONTS['body'], texts)")), 0)
        self.assertEqual(measure_debt(ast.parse("def measure(x):\n    return x\nw = measure(1)")), 0)

    def test_legacy_canary(self):
        self.assertEqual(legacy_debt(ast.parse(
            "from responsive_ui import measure\nw = measure(font, 'x')")), 1)
        self.assertEqual(legacy_debt(ast.parse(
            "import responsive_ui\nw = responsive_ui.measure(font, 'x')")), 0)  # 由 measure_debt 兜住
        self.assertEqual(legacy_debt(ast.parse(
            "from ui.ui_popup import measure_text_width\nw = measure_text_width(font, ['x'])")), 0)

    def test_approx_canary(self):
        self.assertEqual(approx_debt(ast.parse(
            "w = sum(2 if ord(ch) > 0x2E80 else 1 for ch in s)")), 1)
        self.assertEqual(approx_debt(ast.parse("ok = ord(ch) < 32")), 0)
        self.assertEqual(approx_debt(ast.parse("n = sum(ord(c) < 128 for c in text)")), 0)


if __name__ == '__main__':
    unittest.main()
