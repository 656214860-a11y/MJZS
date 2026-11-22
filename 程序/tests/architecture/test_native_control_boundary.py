"""U6 原生控件门禁：浮层／卡片内新代码不得新增自配颜色的 ``tk.Label``／``tk.Frame``。

AST 口径（``production_files_recursive``，不含 tests／tasks_round／维护记录／.wt／.selftmp）：

- ``native_color_debt``：``tk.Label(...)``／``tk.Frame(...)`` 构造（``tkinter.`` 限定
  与裸名 ``Label``／``Frame`` 同罪；``ttk.*`` 走样式系统不在此列）关键字里出现
  颜色类选项的处数——``bg/fg/background/foreground/highlightbackground/highlightcolor/
  insertbackground/selectbackground/selectforeground/disabledforeground/
  activebackground/activeforeground``。
  AST 无法圈定「浮层与卡片内」，口径为全仓棘轮，存量按文件冻结、只减不增。
- 存量冻结 ``NATIVE_BASELINE``（61 处/13 文件，AST 实测；任务书作者正则口径
  ``tk.Label`` 44 处＋``tk.Frame`` 30 处，差异见本轮结果文件：正则把 ``ttk.`` 限定
  与非颜色选项计入，本门禁只认 ``tk`` 原生接收者＋颜色选项）：
  ``app.py``×4、``cell_hover.py``×3、``desktop.py``×6、``desktop_shared_input.py``×2、
  ``ui/desktop_file_card.py``×2、``ui/desktop_idea_bubbles.py``×5、
  ``ui/desktop_page_nav.py``×2、``ui/desktop_shared_menus.py``×14、
  ``ui/pet_cloud.py``×5、``ui/stage_model_picker.py``×13、``ui/ui_popup.py``×2、
  ``ui/ui_status_bar.py``×2（UX-C4 起左区容器和分隔符改用 ttk，由 4 降到 2）、
  ``ui/ui_usage_indicator.py``×1。
  集中在 ``ui/desktop_shared_menus.py`` 与 ``ui/stage_model_picker.py`` 的浮层内部结构
  （任务书 §3.2-5 已核实为浮层构造，冻结不迁移，见 D6）。
- 豁免：``ui_widgets.py``／``ui_tooltip.py``（组件与提示层自身是原生控件定义处），
  其余四件 AUTHORITY 与 ``test_token_boundary`` 口径一致。
- 已知盲区（AST 固有）：``import tkinter as t`` 类别名接收者、``self.Label(...)``
  方法调用、实例级 ``label.configure(bg=...)`` 改写不在口径内。

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

NATIVE_WIDGETS = frozenset({'Label', 'Frame'})
NATIVE_RECEIVERS = frozenset({'tk', 'tkinter', ''})  # '' = 裸名 Label/Frame
NATIVE_COLOR_OPTIONS = frozenset({
    'bg', 'fg', 'background', 'foreground',
    'highlightbackground', 'highlightcolor',
    'insertbackground', 'selectbackground', 'selectforeground',
    'disabledforeground', 'activebackground', 'activeforeground',
})

# U6 AST 实测冻结（只减不增）：见文件头口径说明。
NATIVE_BASELINE = {
    'app.py': 4,
    'cell_hover.py': 3,
    'desktop.py': 6,
    'desktop_shared_input.py': 2,
    'ui/desktop_file_card.py': 2,
    'ui/desktop_idea_bubbles.py': 5,
    'ui/desktop_page_nav.py': 2,
    'ui/desktop_shared_menus.py': 14,
    'ui/pet_cloud.py': 5,
    'ui/stage_model_picker.py': 13,
    'ui/ui_popup.py': 2,
    'ui/ui_status_bar.py': 2,
    'ui/ui_usage_indicator.py': 1,
}


def _call_name_receiver(node: ast.Call):
    """返回 (调用名, 接收者)：裸名接收者为 ''，复杂接收者（``self.x``／``a.b``）为 None。"""
    func = node.func
    if isinstance(func, ast.Attribute):
        receiver = func.value.id if isinstance(func.value, ast.Name) else None
        return func.attr, receiver
    if isinstance(func, ast.Name):
        return func.id, ''
    return '', None


def native_color_debt(tree: ast.AST) -> int:
    """自配颜色的原生 ``tk.Label``／``tk.Frame`` 构造处数。"""
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name, receiver = _call_name_receiver(node)
        if name not in NATIVE_WIDGETS or receiver not in NATIVE_RECEIVERS:
            continue
        if any(kw.arg in NATIVE_COLOR_OPTIONS for kw in node.keywords if kw.arg):
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


class NativeControlBoundaryTests(unittest.TestCase):
    def test_colored_native_controls_only_decrease(self):
        bad = [f'{rel}: {count}>{cap}' for rel, (count, cap) in
               sorted(_overages(_scan(native_color_debt), NATIVE_BASELINE).items())]
        self.assertEqual(bad, [],
                         '浮层／卡片内新代码不得新增自配颜色的 tk.Label／tk.Frame，'
                         '改用 ui_widgets 组件或 ui_theme 样式：' + '; '.join(bad))

    def test_native_color_canary(self):
        self.assertEqual(native_color_debt(ast.parse(
            "w = tk.Label(m, text='x', bg=COLORS['card'], fg=COLORS['ink'])")), 1)
        self.assertEqual(native_color_debt(ast.parse(
            "w = tk.Frame(m, bg=BG, highlightbackground=COLORS['border'])")), 1)
        self.assertEqual(native_color_debt(ast.parse(
            "w = tkinter.Label(m, background=BG)")), 1)
        self.assertEqual(native_color_debt(ast.parse(
            "w = Label(m, bg=BG)")), 1)
        self.assertEqual(native_color_debt(ast.parse(
            "w = ttk.Label(m, style='Muted.TLabel')")), 0)
        self.assertEqual(native_color_debt(ast.parse(
            "w = tk.Label(m, text='x')")), 0)
        self.assertEqual(native_color_debt(ast.parse(
            "w = tk.Frame(m, padx=SPACING['sm'])")), 0)
        self.assertEqual(native_color_debt(ast.parse(
            "w = self.Label(m, bg=BG)")), 0)

    def _run_ratchet_with(self, folder: Path, source: str):
        sample = folder / 'sample_ui.py'
        sample.write_text(textwrap.dedent(source), encoding='utf-8')
        module = sys.modules[__name__]
        case = NativeControlBoundaryTests('test_colored_native_controls_only_decrease')
        with mock.patch.object(module, 'ROOT', folder), \
                mock.patch.object(module, 'production_files_recursive', return_value=(sample,)):
            case.test_colored_native_controls_only_decrease()

    def test_new_native_color_violation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            with self.assertRaises(AssertionError):
                self._run_ratchet_with(folder,
                                       "import tkinter as tk\n"
                                       "w = tk.Label(m, text='x', bg='white')\n")
            with self.assertRaises(AssertionError):
                self._run_ratchet_with(folder,
                                       "import tkinter as tk\n"
                                       "w = tk.Frame(m, bg=BG)\n")
            self._run_ratchet_with(folder,
                                   "from tkinter import ttk\n"
                                   "w = ttk.Label(m, style='Muted.TLabel')\n")


if __name__ == '__main__':
    unittest.main()
