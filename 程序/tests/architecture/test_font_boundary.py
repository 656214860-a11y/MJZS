"""U6 字体门禁：新代码字体规格只取 ``FONTS[...]``／ui_tokens 命名常量，禁止内联字体元组。

AST 口径（``production_files_recursive``，不含 tests／tasks_round／维护记录／.wt／.selftmp）：

- ``font_debt``：两类内联字体元组，各计 1——
  ① 任意调用 ``font=`` 关键字的值子树内含 ``tuple``／``list`` 字面量
  （控件构造、``configure``、``tag_configure``、``tkfont.Font`` 同罪；
  ``font=FONTS['body']``、``font=ICON_FONT`` 等取值式不算）；
  ② 赋值目标名以 ``FONT`` 结尾（不区分大小写，含属性目标与元组解包目标）
  而值子树内含 ``tuple``／``list`` 字面量——``BUBBLE_FONT=('Microsoft YaHei UI',10)``
  常量绕行同罪。
- 存量冻结 ``FONT_BASELINE``（11 处/6 文件，AST 实测；任务书作者正则口径约 10 处/6 文件）：
  ``asset_reference_images.py``×1、``desktop.py``×2、``ui/desktop_idea_bubbles.py``×2、
  ``ui/pet_cloud.py``×2、``ui/ui_part_renderers.py``×2、``ui/ui_stage_popups.py``×2。
  与作者估计的差异：``ui/pet_cloud.py`` 的 ``configure(font=FONT if ... else (FONT[0], STICKER_FONTS[0]))``
  三元表达式内嵌元组，按「值子树含元组」计 1 处，正则口径未必覆盖。
- 豁免：``ui_tokens.py``（``FONTS`` 与 ``*_FONT`` 常量本体）、``ui_theme.py``（主题字体装配）、
  ``ui_widgets.py``／``ui_splash.py``／``ui_tooltip.py``／``ui_icons.py``（组件与提示层即字体定义处），
  与 ``test_token_boundary`` 的 AUTHORITY 口径一致。
- 已知盲区（AST 固有）：``spec=('YaHei',10); font=spec`` 经普通变量间接传递、
  ``f(**{'font': (...)})`` 字典解包不在口径内；新代码一律 ``font=FONTS[...]``
  或 ``NAME_FONT = FONTS[...]``。

坏样本由 canary 用例（谓词级）与 self-audit（临时目录跑真实门禁方法）双重自审。
"""
from __future__ import annotations

import ast
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from tests.architecture._scan import ROOT, production_files_recursive

AUTHORITY_FILES = frozenset({
    'ui_tokens.py', 'ui_theme.py', 'ui_widgets.py',
    'ui_splash.py', 'ui_tooltip.py', 'ui_icons.py',
})

# U6 AST 实测冻结（只减不增）：见文件头口径说明。
FONT_BASELINE = {
    'asset_reference_images.py': 1,
    'desktop.py': 2,
    'ui/desktop_idea_bubbles.py': 2,
    'ui/pet_cloud.py': 2,
    'ui/ui_part_renderers.py': 2,
    'ui/ui_stage_popups.py': 2,
}


def _has_tuple_literal(node: ast.AST) -> bool:
    return any(isinstance(item, (ast.Tuple, ast.List)) for item in ast.walk(node))


def _target_names(target: ast.AST):
    """赋值目标的名字集合：Name／Attribute 取名，Tuple／List 解包递归。"""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, ast.Attribute):
        yield target.attr
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _target_names(element)


def _is_font_assign(node: ast.AST) -> bool:
    if isinstance(node, ast.Assign):
        targets, value = node.targets, node.value
    elif isinstance(node, ast.AnnAssign):
        targets, value = [node.target], node.value
    else:
        return False
    if value is None or not _has_tuple_literal(value):
        return False
    return any(name.upper().endswith('FONT') for target in targets for name in _target_names(target))


def font_debt(tree: ast.AST) -> int:
    """内联字体元组处数：``font=`` 值含元组字面量，或 ``*_FONT`` 赋值值含元组字面量。"""
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            count += sum(1 for kw in node.keywords
                         if kw.arg == 'font' and _has_tuple_literal(kw.value))
        elif _is_font_assign(node):
            count += 1
    return count


def _scan(counter):
    counts = {}
    for path in production_files_recursive():
        relative = path.relative_to(ROOT).as_posix()
        if path.name in AUTHORITY_FILES:
            continue
        count = counter(ast.parse(path.read_text(encoding='utf-8')))
        if count:
            counts[relative] = count
    return counts


def _overages(counts, baseline):
    return {rel: (count, baseline.get(rel, 0)) for rel, count in counts.items()
            if count > baseline.get(rel, 0)}


class FontBoundaryTests(unittest.TestCase):
    def test_inline_font_tuples_only_decrease(self):
        bad = [f'{rel}: {count}>{cap}' for rel, (count, cap) in
               sorted(_overages(_scan(font_debt), FONT_BASELINE).items())]
        self.assertEqual(bad, [],
                         '新代码字体规格必须走 FONTS[...]／ui_tokens 命名常量，'
                         '不得内联字体元组：' + '; '.join(bad))

    def test_font_canary(self):
        self.assertEqual(font_debt(ast.parse(
            "w = tk.Label(m, font=('Microsoft YaHei UI', 10))")), 1)
        self.assertEqual(font_debt(ast.parse(
            "w = ttk.Label(m, font=('Microsoft YaHei UI', 11, 'bold'))")), 1)
        self.assertEqual(font_debt(ast.parse(
            "w.configure(font=FONT if c else (FONT[0], SIZE))")), 1)
        self.assertEqual(font_debt(ast.parse(
            "BUBBLE_FONT = ('Microsoft YaHei UI', 10)")), 1)
        self.assertEqual(font_debt(ast.parse(
            "self.BUBBLE_FONT = ('Microsoft YaHei UI', 9)")), 1)
        self.assertEqual(font_debt(ast.parse(
            "from ui_tokens import FONTS\nw = tk.Label(m, font=FONTS['body'])")), 0)
        self.assertEqual(font_debt(ast.parse(
            "ICON_FONT = FONTS['caption']\nw = tk.Label(m, font=ICON_FONT)")), 0)
        self.assertEqual(font_debt(ast.parse(
            "STICKER_SIZES = (13, 12, 11)\nw = tk.Label(m, font=FONTS['body'])")), 0)

    def _run_ratchet_with(self, folder: Path, source: str):
        sample = folder / 'sample_ui.py'
        sample.write_text(textwrap.dedent(source), encoding='utf-8')
        module = sys.modules[__name__]
        case = FontBoundaryTests('test_inline_font_tuples_only_decrease')
        with mock.patch.object(module, 'ROOT', folder), \
                mock.patch.object(module, 'production_files_recursive', return_value=(sample,)):
            case.test_inline_font_tuples_only_decrease()

    def test_new_font_violation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            with self.assertRaises(AssertionError):
                self._run_ratchet_with(folder,
                                       "import tkinter as tk\n"
                                       "w = tk.Label(m, font=('Microsoft YaHei UI', 10))\n")
            with self.assertRaises(AssertionError):
                self._run_ratchet_with(folder,
                                       "BUBBLE_FONT = ('Microsoft YaHei UI', 10)\n")
            self._run_ratchet_with(folder,
                                   "from ui_tokens import FONTS\n"
                                   "w = tk.Label(m, font=FONTS['body'])\n")


if __name__ == '__main__':
    unittest.main()
