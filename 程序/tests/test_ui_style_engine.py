# -*- coding: utf-8 -*-
"""UI 批次 2：样式引擎收口。

钉住四件事：
1. 按钮／输入／焦点样式只在 ``ui_widgets.setup_styles()`` 一处定义，
   ``ui_theme.apply()`` 只装主题后调用它；
2. 真 Tk 根窗口下 Primary／Secondary 按钮与 TEntry／SelectBox／TSpinbox 的
   ``winfo_reqheight()`` 落在 32±2px（非 100% 缩放时按 ``tk scaling`` 折算）；
3. 所有按钮样式的 ``focuscolor`` 都是 ``COLORS['focus']``；
4. 导航／侧栏／主区按钮样式常态无可见边框（solid 边框用自身底色），焦点时边框为
   ``COLORS['focus']``，且仍保持 32±2px 行高；
5. ``NotificationDispatcher.error()`` 默认非模态；主窗口默认 1280×900（R3060 加高）、
   最小 1024×600，弹窗最小尺寸不再降到 1×1。
"""
from __future__ import annotations

import ast
import inspect
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

import ui_theme
import ui_widgets
from ui_tokens import (COLORS, COMBOBOX_CONTROL_PADDING,
                       CONTROL_HEIGHT, CONTROL_PADDING_Y, DESKTOP_LAYOUT,
                       DIALOG_MIN_HEIGHT, DIALOG_MIN_WIDTH)

ROOT = Path(__file__).resolve().parents[1]

BUTTON_STYLES = (
    "TButton", "Compact.TButton", "Asset.TButton", "ProjectAction.TButton",
    "Primary.TButton", "Tokens.Primary.TButton",
    "Secondary.TButton", "Tokens.Secondary.TButton",
    "Tokens.Danger.TButton", "Tokens.Icon.TButton",
    "Send.TButton", "Selected.Compact.TButton", "Highlight.TButton",
    "Nav.TButton", "Sub.Nav.TButton",
    "Selected.Nav.TButton", "Selected.Sub.Nav.TButton",
)
# 导航、侧栏与主区动作按钮沿用旧版扁平外观：常态无可见边框，只有焦点环。
FLAT_BUTTON_STYLES = (
    "TButton", "Compact.TButton", "ProjectAction.TButton",
    "Nav.TButton", "Sub.Nav.TButton",
    "Selected.Nav.TButton", "Selected.Sub.Nav.TButton",
)
CONTROL_STYLE_SUFFIXES = (".TButton", ".TEntry", ".TCombobox", ".TSpinbox")
CONTROL_STYLE_NAMES = {
    "TButton", "TEntry", "TCombobox", "TSpinbox", "Tokens.Combobox.TCombobox",
}


def _configured_style_names(path):
    """AST 收集 ``style.configure('名字', ...)``／``style.map('名字', ...)``。

    ui_widgets 通过 ``_configure_button(style, '名字', ...)`` 与
    ``_configure_combobox(style, '名字', ...)`` 两个助手定义样式，一并计入。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (isinstance(node.func, ast.Attribute) and node.func.attr in {"configure", "map"}
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"style", "s"}):
            index = 0
        elif (isinstance(node.func, ast.Name)
              and node.func.id in {"_configure_button", "_configure_combobox"}):
            index = 1
        else:
            continue
        if len(node.args) > index:
            argument = node.args[index]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                names.add(argument.value)
    return names


class StyleSourceTests(unittest.TestCase):
    """同名样式只能出现在 ui_widgets；ui_theme 不得残留第二套按钮／输入样式。"""

    def test_button_and_input_styles_are_defined_only_in_ui_widgets(self):
        widgets = _configured_style_names(ROOT / "ui_widgets.py")
        theme = _configured_style_names(ROOT / "ui" / "ui_theme.py")
        canonical = CONTROL_STYLE_NAMES | set(BUTTON_STYLES)

        self.assertEqual(sorted(canonical - widgets), [],
                         "这些样式必须在 ui_widgets.setup_styles() 里定义")
        duplicates = sorted(name for name in theme
                            if name in canonical
                            or (name.endswith(CONTROL_STYLE_SUFFIXES)
                                and not name.endswith("TCheckbutton")))
        self.assertEqual(duplicates, [],
                         "ui_theme.apply() 不得再定义按钮／输入样式：" + ", ".join(duplicates))

    def test_ui_theme_apply_delegates_to_setup_styles(self):
        tree = ast.parse((ROOT / "ui" / "ui_theme.py").read_text(encoding="utf-8"))
        apply_node = next(node for node in ast.walk(tree)
                          if isinstance(node, ast.FunctionDef) and node.name == "apply")
        called = {node.func.id for node in ast.walk(apply_node)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertIn("setup_styles", called,
                      "ui_theme.apply() 必须调用 ui_widgets.setup_styles()")


class ControlGeometryTests(unittest.TestCase):
    """真 Tk 实测：36±2px，按当前 tk scaling 折算。"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        ui_theme.apply(self.root)

    def _expected(self):
        scaling = float(self.root.tk.call("tk", "scaling"))
        # 100% DPI（96 dpi）对应 tk scaling = 96/72 = 1.333…
        factor = scaling / (96 / 72.0)
        return CONTROL_HEIGHT * factor, 2 * factor, scaling

    def test_primary_secondary_entry_combobox_and_spinbox_request_36px(self):
        widgets = {
            "Primary": ui_widgets.PrimaryButton(self.root, text="主按钮"),
            "Secondary": ui_widgets.SecondaryButton(self.root, text="次按钮"),
            "TEntry": ttk.Entry(self.root),
            "LineInput": ui_widgets.LineInput(self.root, placeholder="项目名称"),
            "SelectBox": ui_widgets.SelectBox(self.root, values=("甲", "乙")),
            "TSpinbox": ttk.Spinbox(self.root, from_=0, to=9),
        }
        self.root.update_idletasks()
        expected, tolerance, scaling = self._expected()
        for label, widget in widgets.items():
            with self.subTest(widget=label):
                actual = widget.winfo_reqheight()
                self.assertLessEqual(
                    abs(actual - expected), tolerance,
                    "%s 请求高度 %dpx，期望 %.1f±%.1f（tk scaling=%.4f）；"
                    "控件高度=字体行高+2×上下内边距+边框"
                    % (label, actual, expected, tolerance, scaling))

    def test_all_button_styles_share_the_focus_token(self):
        style = ttk.Style(self.root)
        for name in BUTTON_STYLES:
            with self.subTest(style=name):
                self.assertEqual(str(style.lookup(name, "focuscolor")), COLORS["focus"])

    def test_geometry_tokens_are_derived_from_the_4px_scale(self):
        self.assertEqual(CONTROL_PADDING_Y, 8)
        self.assertEqual(COMBOBOX_CONTROL_PADDING[1], CONTROL_PADDING_Y)


class FlatButtonStyleTests(unittest.TestCase):
    """导航／侧栏／主区按钮：圆角图元取代 raised 边框，常态无可见边框，仅键盘焦点环。"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        ui_theme.apply(self.root)
        self.style = ttk.Style(self.root)

    def test_navigation_sidebar_and_project_buttons_have_no_visible_border(self):
        for name in FLAT_BUTTON_STYLES:
            with self.subTest(style=name):
                layout = self.style.layout(name)
                self.assertTrue(layout, "%s 必须使用自定义圆角图元布局" % name)
                element = str(layout[0][0])
                self.assertIn("Drama.Rounded", element,
                              "%s 必须使用圆角图元，不得退回 raised 边框" % name)

    def test_flat_button_focus_ring_uses_the_focus_token(self):
        for name in FLAT_BUTTON_STYLES:
            with self.subTest(style=name):
                self.assertEqual(str(self.style.lookup(name, "focuscolor")),
                                 COLORS["focus"],
                                 "%s 的焦点环必须使用 color.focus" % name)

    def test_flat_button_styles_keep_the_36px_row_height(self):
        expected, tolerance, scaling = self._expected()
        for name in FLAT_BUTTON_STYLES:
            button = ttk.Button(self.root, text="导航", style=name)
            self.root.update_idletasks()
            with self.subTest(style=name):
                actual = button.winfo_reqheight()
                self.assertLessEqual(abs(actual - expected), tolerance,
                                     "%s 请求高度 %dpx，期望 %.1f±%.1f（tk scaling=%.4f）"
                                     % (name, actual, expected, tolerance, scaling))

    def _expected(self):
        scaling = float(self.root.tk.call("tk", "scaling"))
        factor = scaling / (96 / 72.0)
        return CONTROL_HEIGHT * factor, 2 * factor, scaling


class NotificationDefaultTests(unittest.TestCase):
    class _Status:
        def __init__(self):
            self.values = []

        def set(self, value):
            self.values.append(value)

    class _Dialogs:
        def __init__(self):
            self.calls = []

        def showerror(self, title, text, parent=None):
            self.calls.append(("error", title, text, parent))

    def test_error_defaults_to_non_modal_and_keeps_the_detail_in_the_status_bar(self):
        status, dialogs = self._Status(), self._Dialogs()
        notifier = ui_widgets.NotificationDispatcher(status, dialogs=dialogs)
        default = inspect.signature(ui_widgets.NotificationDispatcher.error).parameters["modal"].default
        self.assertIs(default, False, "可恢复错误默认不得锁住界面")
        message = notifier.error("网络断开，请检查代理后重试")
        self.assertEqual(message, "网络断开，请检查代理后重试")
        self.assertEqual(status.values, [message])
        self.assertEqual(dialogs.calls, [], "默认非模态时不得弹出系统模态框")

    def test_explicit_modal_true_still_blocks(self):
        status, dialogs = self._Status(), self._Dialogs()
        notifier = ui_widgets.NotificationDispatcher(status, dialogs=dialogs)
        notifier.error("必须由用户确认", title="阻断", modal=True)
        self.assertEqual(dialogs.calls, [("error", "阻断", "必须由用户确认", None)])


class WindowPolicyTests(unittest.TestCase):
    def test_main_window_default_and_minimum_tokens(self):
        # R3060：默认高度 800→900。C19（2026-11-27）：最小宽 800→1024，高仍 600。
        self.assertEqual((DESKTOP_LAYOUT["default_width"], DESKTOP_LAYOUT["default_height"]),
                         (1280, 900))
        self.assertEqual((DESKTOP_LAYOUT["min_width"], DESKTOP_LAYOUT["min_height"]),
                         (1024, 600))
        self.assertEqual(ui_theme.main_window_size(1920, 1080), (1280, 900))
        # 可用区不足时按 token 边距收缩，不把默认值硬塞进屏幕。
        self.assertEqual(ui_theme.main_window_size(1366, 728), (1280, 680))

    def test_real_main_window_uses_the_policy_and_keeps_1024x600_minimum(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.minsize(DESKTOP_LAYOUT["min_width"], DESKTOP_LAYOUT["min_height"])
        ui_theme.install_window_placement(root)
        for _ in range(6):
            root.update()
        left, top, right, bottom = ui_theme._work_area(root, root)
        placed = ui_theme.main_window_size(right - left, bottom - top)
        self.assertEqual((root.winfo_width(), root.winfo_height()), placed,
                         "主窗口首次尺寸应为 1280×900（屏幕放不下时收缩）")
        # 方案 A：token 最小 1024×600；工作区放不下首次尺寸时，最小尺寸随首次尺寸收缩，不改这条规则。
        self.assertEqual(root.minsize(), (min(DESKTOP_LAYOUT["min_width"], placed[0]),
                                           min(DESKTOP_LAYOUT["min_height"], placed[1])))

    def test_popup_minimum_is_not_lowered_to_one_by_one(self):
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.withdraw()
        ui_theme.install_window_placement(root)
        popup = tk.Toplevel(root)
        self.addCleanup(lambda: popup.winfo_exists() and popup.destroy())
        popup.geometry("100x80+10+10")
        for _ in range(6):
            root.update()
        self.assertEqual(popup.minsize(), (DIALOG_MIN_WIDTH, DIALOG_MIN_HEIGHT))
        self.assertNotEqual(popup.minsize(), (1, 1))
        self.assertGreaterEqual(DIALOG_MIN_WIDTH, 240)
        self.assertGreaterEqual(DIALOG_MIN_HEIGHT, 160)


if __name__ == "__main__":
    unittest.main(verbosity=2)
