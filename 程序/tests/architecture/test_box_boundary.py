"""U5 Box 框体边界：``Box.TFrame`` 只在 ``ui/ui_theme.py`` 定义，聊天／内容／列表框走 ``box_frame`` 入口。

AST 口径（``production_files_recursive``，不含 tests／tasks_round／维护记录）：

- ``literal_debt``：``'Box.TFrame'`` 字符串字面量——``ui/ui_theme.py`` 为样式定义本体豁免，
  其余生产文件零容忍（迁移后全仓应为 0）。
- ``border_debt``：``tk``／``ttk`` 的 ``Frame``／``Label``（含裸名 ``Frame``／``Label``）构造上
  ``relief`` 取 {solid,ridge,sunken,raised,groove} 且 ``borderwidth`` 为 1–3 整数字面量的
  「自拼 1px 边框」；按文件冻结只减不增（存量：``cell_hover.py`` ×1、``ui/skill_panel.py`` ×2）。
- 正向锚点：``ui/desktop_writing_page.py`` 的聊天框必须经 ``box_frame`` 创建。

坏样本由 canary 用例自审。
"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, production_files_recursive

EXEMPT = {'ui/ui_theme.py'}
BORDER_RELIEFS = frozenset({'solid', 'ridge', 'sunken', 'raised', 'groove'})
# 存量冻结（D6 不批量迁移）：cell_hover.py:397 tk.Label 放大镜描边；
# ui/skill_panel.py:241/244 两处 ttk.Frame 的 relief/borderwidth 为 ttk 忽略的死选项。
BORDER_BASELINE = {'cell_hover.py': 1, 'ui/skill_panel.py': 2}


def literal_debt(tree: ast.AST) -> int:
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and node.value == 'Box.TFrame')


def _is_border_widget_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return (func.attr in {'Frame', 'Label'}
                and isinstance(func.value, ast.Name) and func.value.id in {'tk', 'ttk'})
    return isinstance(func, ast.Name) and func.id in {'Frame', 'Label'}


def border_debt(tree: ast.AST) -> int:
    count = 0
    for node in ast.walk(tree):
        if not _is_border_widget_call(node):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords}
        relief, width = kwargs.get('relief'), kwargs.get('borderwidth')
        if (isinstance(relief, ast.Constant) and relief.value in BORDER_RELIEFS
                and isinstance(width, ast.Constant) and isinstance(width.value, int)
                and not isinstance(width.value, bool) and 1 <= width.value <= 3):
            count += 1
    return count


def _scan(counter):
    counts = {}
    for path in production_files_recursive():
        relative = path.relative_to(ROOT).as_posix()
        if relative in EXEMPT:
            continue
        count = counter(ast.parse(path.read_text(encoding='utf-8')))
        if count:
            counts[relative] = count
    return counts


def _overages(counts, baseline):
    return {rel: (count, baseline.get(rel, 0)) for rel, count in counts.items()
            if count > baseline.get(rel, 0)}


class BoxBoundaryTests(unittest.TestCase):
    def test_box_style_literal_is_zero_outside_theme(self):
        bad = [f'{rel}: {count}' for rel, count in sorted(_scan(literal_debt).items())]
        self.assertEqual(bad, [],
                         'Box.TFrame 只能由 ui_theme 定义；页面须走 box_frame 入口：' + '; '.join(bad))

    def test_hand_rolled_borders_only_decrease(self):
        bad = [f'{rel}: {count}>{cap}' for rel, (count, cap) in
               sorted(_overages(_scan(border_debt), BORDER_BASELINE).items())]
        self.assertEqual(bad, [],
                         '聊天框／内容框／列表框不得自拼 1px 边框，改走 box_frame：' + '; '.join(bad))

    def test_writing_page_chat_box_uses_entry(self):
        tree = ast.parse((ROOT / 'ui' / 'desktop_writing_page.py').read_text(encoding='utf-8'))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and ((isinstance(node.func, ast.Name) and node.func.id == 'box_frame')
                      or (isinstance(node.func, ast.Attribute) and node.func.attr == 'box_frame'))]
        self.assertTrue(calls, '剧本页聊天框必须经 ui_theme.box_frame 创建')

    def test_literal_canary(self):
        self.assertEqual(literal_debt(ast.parse("f = ttk.Frame(m, style='Box.TFrame')")), 1)
        self.assertEqual(literal_debt(ast.parse('f = ttk.Frame(m, style="Box.TFrame")')), 1)
        self.assertEqual(literal_debt(ast.parse("f = ttk.Frame(m, style='Card.TFrame')")), 0)

    def test_border_canary(self):
        self.assertEqual(border_debt(ast.parse(
            "f = tk.Frame(m, relief='solid', borderwidth=1)")), 1)
        self.assertEqual(border_debt(ast.parse(
            "f = ttk.Label(m, relief='ridge', borderwidth=2, bg='white')")), 1)
        self.assertEqual(border_debt(ast.parse(
            "Frame(m, relief='sunken', borderwidth=3)")), 1)
        self.assertEqual(border_debt(ast.parse(
            "f = tk.Frame(m, relief='flat', borderwidth=1)")), 0)
        self.assertEqual(border_debt(ast.parse(
            "f = tk.Frame(m, relief='solid', borderwidth=8)")), 0)
        self.assertEqual(border_debt(ast.parse(
            "f = tk.Frame(m, relief='solid')")), 0)
        self.assertEqual(border_debt(ast.parse(
            "s = ttk.Style(); s.configure('X', relief='solid', borderwidth=1)")), 0)


if __name__ == '__main__':
    unittest.main()
