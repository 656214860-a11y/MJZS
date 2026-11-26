"""U6 表单控件门禁：``Checkbutton``／``Radiobutton``／``Scale``／``Spinbox``／``Notebook``
（另含 ``Listbox`` 单独记录）新代码只能用 ui_theme 已登记样式名，不得内联配置外观。

AST 口径（``production_files_recursive``，不含 tests／tasks_round／维护记录／.wt／.selftmp）：

- ``form_debt``：表单控件构造各计 1——
  ① ``tk.``／``tkinter.`` 限定或裸名（无 ``ttk.`` 限定即视为原生控件、无样式通道）；
  ② ``ttk.`` 控件带外观关键字（颜色／``relief``／``borderwidth``／``padx``／``pady``／
  ``highlight*``／``selectcolor``／``active*``／``troughcolor``／``sliderrelief``／
  ``buttoncolor``／``readonlybackground``／``disabledforeground`` 等；
  ``font`` 归字体门禁不在此列）；
  ③ ``ttk.`` 控件 ``style=`` 取非字符串字面量，或字面量不在 ``ALLOWED_STYLES``
  （ttk 内建样式名 ∪ ``ui_theme``／``ui_widgets``／``ui_composer_style`` 经
  ``configure``／``map``／``layout`` 登记的样式名，本测试导入时实测收割）。
- ``style_config_debt``：``.configure``／``.map``／``.layout`` 首参为字符串字面量
  且命中表单控件样式名子串（``Checkbutton``／``Radiobutton``／``Scale``／``Spinbox``／
  ``Notebook``／``Listbox``）的局部样式改写——主题层之外再配置同罪。存量为零，新增即红。
- 存量冻结 ``FORM_BASELINE``（5 处/5 文件，AST 实测，全部 ``tk.Listbox`` 原生控件）：
  ``ui/asset_reference_import.py``、``ui/desktop_writing_snapshots.py``、
  ``ui/script_outline.py``、``ui/skill_panel.py``、``ui/skill_panel_import.py``
  ——任务书作者正则另记 ``Listbox`` 3 处，本门禁按构造点实测为 5 处。
  任务书作者统计的 25 处/11 文件为 Checkbutton/Radiobutton/Scale/Spinbox/Notebook
  全部使用点；其中 ``ttk.`` 控件无外观选项、样式经主题继承或显式
  ``style='TCheckbutton'``，属合规不计债。
- 豁免：AUTHORITY 六件（``ui_theme``／``ui_widgets`` 自身即样式登记处，豁免否则
  ``style_config_debt`` 必然命中其 ``configure('TCheckbutton', ...)``）。
- 已知盲区（AST 固有）：``import tkinter.ttk as t`` 类别名接收者、实例级
  ``widget.configure(bg=...)`` 外观改写、``style=`` 变量间接传递不在口径内。

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
    'ui_tooltip.py', 'ui_icons.py',
})

FORM_WIDGETS = frozenset({
    'Checkbutton', 'Radiobutton', 'Scale', 'Spinbox', 'Notebook', 'Listbox',
})
# 外观关键字（``font`` 归字体门禁；``style`` 单列判定）。
FORM_APPEARANCE_OPTIONS = frozenset({
    'bg', 'fg', 'background', 'foreground', 'bd', 'relief', 'borderwidth',
    'padx', 'pady', 'ipadx', 'ipady',
    'highlightbackground', 'highlightcolor', 'highlightthickness',
    'selectcolor', 'selectbackground', 'selectforeground',
    'activebackground', 'activeforeground', 'disabledforeground',
    'troughcolor', 'sliderrelief', 'buttoncolor', 'readonlybackground',
    'insertbackground',
})
# ttk 内建样式名（未在主题层 configure 的也合法）。
TTK_BUILTIN_STYLES = frozenset({
    'TCheckbutton', 'TRadiobutton', 'TScale', 'TSpinbox',
    'TNotebook', 'TNotebook.Tab', 'TListbox',
    'Horizontal.TScale', 'Vertical.TScale',
})
# 主题层样式登记源：configure／map／layout 首参字符串即已登记样式名。
STYLE_SOURCE_FILES = ('ui/ui_theme.py', 'ui_widgets.py', 'ui/ui_composer_style.py')
STYLE_CONFIG_METHODS = frozenset({'configure', 'map', 'layout'})
STYLE_HARVEST_METHODS = frozenset({'configure', 'map', 'layout'})
FORM_STYLE_MARKERS = ('Checkbutton', 'Radiobutton', 'Scale', 'Spinbox', 'Notebook', 'Listbox')

# U6 AST 实测冻结（只减不增）：见文件头口径说明。
FORM_BASELINE = {
    'ui/asset_reference_import.py': 1,
    'ui/desktop_writing_snapshots.py': 1,
    'ui/script_outline.py': 1,
    'ui/skill_panel.py': 1,
    'ui/skill_panel_import.py': 1,
}
# 局部样式改写存量为零：任何新增即红。
STYLE_CONFIG_BASELINE = {}


def _registered_style_names() -> frozenset:
    """ttk 内建样式名 ∪ 主题层 ``configure``／``map``／``layout`` 首参登记的样式名。"""
    names = set(TTK_BUILTIN_STYLES)
    for relative in STYLE_SOURCE_FILES:
        path = ROOT / relative
        if not path.is_file():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in STYLE_HARVEST_METHODS and node.args):
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names.add(first.value)
    return frozenset(names)


ALLOWED_STYLES = _registered_style_names()


def _call_name_receiver(node: ast.Call):
    """返回 (调用名, 接收者)：裸名接收者为 ''，复杂接收者（``self.x``／``a.b``）为 None。"""
    func = node.func
    if isinstance(func, ast.Attribute):
        receiver = func.value.id if isinstance(func.value, ast.Name) else None
        return func.attr, receiver
    if isinstance(func, ast.Name):
        return func.id, ''
    return '', None


def _style_is_registered(value: ast.AST) -> bool:
    return (isinstance(value, ast.Constant) and isinstance(value.value, str)
            and value.value in ALLOWED_STYLES)


def form_debt(tree: ast.AST) -> int:
    """表单控件违规构造处数：原生／裸名，或 ttk 控件带外观选项／未登记样式名。"""
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name, receiver = _call_name_receiver(node)
        if name not in FORM_WIDGETS:
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        if receiver in {'tk', 'tkinter', ''}:
            count += 1
            continue
        if receiver != 'ttk':
            continue
        if any(key in FORM_APPEARANCE_OPTIONS for key in keywords):
            count += 1
            continue
        style = keywords.get('style')
        if style is not None and not _style_is_registered(style):
            count += 1
    return count


def style_config_debt(tree: ast.AST) -> int:
    """主题层之外对表单控件样式名的 ``configure``／``map``／``layout`` 改写处数。"""
    count = 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in STYLE_CONFIG_METHODS and node.args):
            continue
        first = node.args[0]
        if (isinstance(first, ast.Constant) and isinstance(first.value, str)
                and any(marker in first.value for marker in FORM_STYLE_MARKERS)):
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


class FormControlBoundaryTests(unittest.TestCase):
    def test_form_controls_only_decrease(self):
        bad = [f'{rel}: {count}>{cap}' for rel, (count, cap) in
               sorted(_overages(_scan(form_debt), FORM_BASELINE).items())]
        self.assertEqual(bad, [],
                         '表单控件新代码只能用 ui_theme 已登记样式名，不得内联配置外观：'
                         + '; '.join(bad))

    def test_local_form_style_reconfigure_is_zero(self):
        bad = [f'{rel}: {count}>{cap}' for rel, (count, cap) in
               sorted(_overages(_scan(style_config_debt), STYLE_CONFIG_BASELINE).items())]
        self.assertEqual(bad, [],
                         '表单控件样式只能由 ui_theme／ui_widgets 登记，'
                         '业务代码不得局部 configure/map/layout 改写：' + '; '.join(bad))

    def test_form_canary(self):
        self.assertEqual(form_debt(ast.parse("w = tk.Checkbutton(m, bg='white')")), 1)
        self.assertEqual(form_debt(ast.parse("w = Checkbutton(m)")), 1)
        self.assertEqual(form_debt(ast.parse(
            "w = ttk.Checkbutton(m, style='TCheckbutton', selectcolor='red')")), 1)
        self.assertEqual(form_debt(ast.parse(
            "w = ttk.Checkbutton(m, style='Fancy.Checkbutton')")), 1)
        self.assertEqual(form_debt(ast.parse(
            "w = ttk.Checkbutton(m, style=STYLE_NAME)")), 1)
        self.assertEqual(form_debt(ast.parse(
            "w = ttk.Checkbutton(m, style='TCheckbutton')")), 0)
        self.assertEqual(form_debt(ast.parse(
            "w = ttk.Checkbutton(m, text='自动', variable=v)")), 0)
        self.assertEqual(form_debt(ast.parse(
            "w = ttk.Spinbox(m, from_=0, to=10)")), 0)

    def test_style_config_canary(self):
        self.assertEqual(style_config_debt(ast.parse(
            "s.configure('TCheckbutton', bg='red')")), 1)
        self.assertEqual(style_config_debt(ast.parse(
            "s.map('Tokens.Composer.Send.TButton', foreground=[])")), 0)
        self.assertEqual(style_config_debt(ast.parse(
            "s.configure(style_name, bg='red')")), 0)

    def _run_ratchet_with(self, folder: Path, source: str, method: str):
        sample = folder / 'sample_ui.py'
        sample.write_text(textwrap.dedent(source), encoding='utf-8')
        module = sys.modules[__name__]
        case = FormControlBoundaryTests(method)
        with mock.patch.object(module, 'ROOT', folder), \
                mock.patch.object(module, 'production_files_recursive', return_value=(sample,)):
            getattr(case, method)()

    def test_new_form_violation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            with self.assertRaises(AssertionError):
                self._run_ratchet_with(folder, "w = tk.Checkbutton(m)\n",
                                       'test_form_controls_only_decrease')
            with self.assertRaises(AssertionError):
                self._run_ratchet_with(folder,
                                       "s.configure('TCheckbutton', bg='red')\n",
                                       'test_local_form_style_reconfigure_is_zero')
            self._run_ratchet_with(folder,
                                   "w = ttk.Checkbutton(m, style='TCheckbutton')\n",
                                   'test_form_controls_only_decrease')


if __name__ == '__main__':
    unittest.main()
