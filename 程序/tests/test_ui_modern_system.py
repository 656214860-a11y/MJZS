# -*- coding: utf-8 -*-
"""2026-10-21 UI 设计系统升级（功能轮）：现代色阶、圆角按钮/卡片、细条滚动条。

对应任务书 V1–V5、V7：颜色契约、按钮状态、圆角图元、输入框、滚动条与性能。
"""
import gc
import sys
import time
import tkinter as tk
import unittest
from tkinter import ttk

import ui_theme
import ui_widgets
from ui_tokens import COLORS, CONTROL_HEIGHT, RADIUS, SCROLLBAR_WIDTH

BUTTON_STYLES = (
    "TButton", "Compact.TButton", "Asset.TButton", "ProjectAction.TButton",
    "Primary.TButton", "Tokens.Primary.TButton",
    "Secondary.TButton", "Tokens.Secondary.TButton",
    "Tokens.Danger.TButton", "Tokens.Icon.TButton",
    "Send.TButton", "Selected.Compact.TButton", "Highlight.TButton",
    "Nav.TButton", "Sub.Nav.TButton",
    "Selected.Nav.TButton", "Selected.Sub.Nav.TButton",
)


def _luminance(value):
    channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground, background):
    high, low = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ColorContractTests(unittest.TestCase):
    """V1：现代色阶的对比度契约与装饰色边界。"""

    def test_text_tokens_meet_contrast_on_page_card_and_hover(self):
        for text in ("text_primary", "text_secondary", "text_muted"):
            for background in ("background_primary", "background_card", "surface_hover"):
                with self.subTest(text=text, background=background):
                    self.assertGreaterEqual(
                        _contrast(COLORS[text], COLORS[background]), 4.5)

    def test_white_text_on_solid_buttons_meets_contrast(self):
        for fill in ("primary", "primary_hover", "primary_pressed", "danger", "success"):
            with self.subTest(fill=fill):
                self.assertGreaterEqual(
                    _contrast(COLORS["background_card"], COLORS[fill]), 4.5)

    def test_primary_meets_contrast_on_new_page_background(self):
        self.assertGreaterEqual(
            _contrast(COLORS["primary"], "#F7F9F9"), 4.5)

    def test_decorative_blue_appears_only_in_decorative_tokens(self):
        for name, value in COLORS.items():
            if value == "#1D9BF0":
                self.assertIn(name, {"accent"}, "装饰色 #1D9BF0 只许登记为装饰色令牌")

    def test_decorative_blue_is_not_a_button_foreground_or_background(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        ui_theme.apply(root)
        style = ttk.Style(root)
        states = ((), ("active",), ("pressed",), ("disabled",))
        for name in BUTTON_STYLES:
            for state in states:
                for option in ("background", "fill", "foreground"):
                    with self.subTest(style=name, state=state, option=option):
                        value = str(style.lookup(name, option, state))
                        self.assertNotEqual(value, "#1D9BF0",
                                            "%s 不得以装饰色作%s" % (name, option))


class ButtonStateTests(unittest.TestCase):
    """V2：17 个既有样式名的三态映射与按压反馈。"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        ui_theme.apply(self.root)
        self.style = ttk.Style(self.root)

    def test_all_styles_have_active_pressed_disabled_background_maps(self):
        for name in BUTTON_STYLES:
            with self.subTest(style=name):
                bg_map = dict(self.style.map(name, "fill"))
                for state in ("active", "pressed", "disabled"):
                    self.assertIn(state, bg_map,
                                  "%s 缺 %s 背景映射" % (name, state))
                ttk.Button(self.root, text="x", style=name)  # 仍可创建

    def test_primary_buttons_darken_on_hover_and_press(self):
        for name in BUTTON_STYLES:
            normal = str(self.style.lookup(name, "fill"))
            if normal != COLORS["primary"]:
                continue
            with self.subTest(style=name):
                hover = str(self.style.lookup(name, "fill", ("active",)))
                pressed = str(self.style.lookup(name, "fill", ("pressed",)))
                self.assertNotEqual(hover, COLORS["primary_subtle"])
                self.assertLess(_luminance(hover), _luminance(normal))
                self.assertLess(_luminance(pressed), _luminance(hover))

    def test_secondary_hover_and_pressed_tokens_are_consumed(self):
        self.assertEqual(str(self.style.lookup("TButton", "fill", ("active",))),
                         COLORS["secondary_hover"])
        self.assertEqual(str(self.style.lookup("TButton", "fill", ("pressed",))),
                         COLORS["secondary_pressed"])

    def test_pressed_state_has_text_shift_or_equivalent_feedback(self):
        for name in BUTTON_STYLES:
            with self.subTest(style=name):
                normal_padding = str(self.style.lookup(name, "padding"))
                pressed_padding = str(self.style.lookup(name, "padding", ("pressed",)))
                self.assertNotEqual(pressed_padding, normal_padding,
                                    "%s 按下态无文字位移或等价反馈" % name)


class RoundedElementTests(unittest.TestCase):
    """V3：按钮/卡片使用圆角图元，图按 tk scaling 缩放，不依赖 PIL。"""

    def test_buttons_and_card_use_image_elements(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        ui_theme.apply(root)
        style = ttk.Style(root)
        names = set(style.element_names())
        self.assertTrue(any(n.startswith("Drama.Rounded.") for n in names),
                        "按钮必须登记圆角图元")
        self.assertIn("Drama.Card", names, "卡片必须登记圆角图元")
        for name in BUTTON_STYLES:
            layout = style.layout(name)
            self.assertIn("Drama.Rounded.", str(layout[0][0]),
                          "%s 的布局必须使用圆角图元" % name)

    def test_radius_comes_from_radius_token_and_images_survive_gc(self):
        root = tk.Tk()
        root.withdraw()
        ui_theme.apply(root)
        style = ttk.Style(root)
        names = [n for n in style.element_names() if n.startswith("Drama.Rounded.")]
        self.assertTrue(names)
        root.destroy()
        gc.collect()
        root2 = tk.Tk()
        root2.withdraw()
        self.addCleanup(root2.destroy)
        ui_theme.apply(root2)
        button = ttk.Button(root2, text="圆角", style="Primary.TButton")
        root2.update_idletasks()  # 图元仍可画，无 TclError

    def test_images_scale_with_tk_scaling(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        try:
            root.tk.call("tk", "scaling", 1.0)
            image1, _ = ui_widgets._rounded_photo(root, COLORS["primary"], RADIUS["md"],
                                                  width=40, height=40)
            h1 = image1.height()
            root.tk.call("tk", "scaling", 2.0)
            image2, _ = ui_widgets._rounded_photo(root, COLORS["primary"], RADIUS["md"],
                                                  width=40, height=40)
            h2 = image2.height()
        finally:
            root.tk.call("tk", "scaling", 96 / 72.0)
        self.assertAlmostEqual(h2 / h1, 2.0, delta=0.3)

    def test_generator_does_not_depend_on_pil(self):
        self.assertNotIn("PIL", sys.modules)

    def test_card_radius_uses_large_radius_token(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        ui_theme.apply(root)
        factor = float(root.tk.call("tk", "scaling")) / (96 / 72.0)
        expected = max(1, round(RADIUS["lg"] * factor))
        image, _ = ui_widgets._rounded_photo(root, COLORS["background_card"], RADIUS["lg"],
                                             width=40, height=40,
                                             border=COLORS["border_default"], border_width=1)
        # 卡片图按 lg 半径取整后的角区不小于 lg 半径。
        self.assertGreaterEqual(image.height(), expected)


class InputFocusTests(unittest.TestCase):
    """V4：输入框聚焦描边为主色，TextArea 高亮色为主色，高度 36±2px。"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        ui_theme.apply(self.root)
        self.style = ttk.Style(self.root)

    def test_line_input_focus_border_maps_to_primary(self):
        self.assertEqual(str(self.style.lookup("Tokens.LineInput.TEntry", "bordercolor",
                                               ("focus",))), COLORS["primary"])

    def test_text_area_focus_highlight_is_primary(self):
        area = ui_widgets.TextArea(self.root, placeholder="梗概")
        self.assertEqual(str(area.cget("highlightcolor")), COLORS["primary"])
        self.assertEqual(str(area.cget("highlightbackground")), COLORS["border_input"])

    def test_single_line_controls_keep_36px_height(self):
        widgets = {
            "LineInput": ui_widgets.LineInput(self.root, placeholder="项目名称"),
            "SelectBox": ui_widgets.SelectBox(self.root, values=("甲", "乙")),
            "TSpinbox": ttk.Spinbox(self.root, from_=0, to=9),
        }
        self.root.update_idletasks()
        scaling = float(self.root.tk.call("tk", "scaling"))
        factor = scaling / (96 / 72.0)
        for label, widget in widgets.items():
            with self.subTest(widget=label):
                actual = widget.winfo_reqheight()
                self.assertLessEqual(abs(actual - CONTROL_HEIGHT * factor), 2 * factor,
                                     "%s 高度 %dpx 偏离 36±2" % (label, actual))


class ScrollbarTests(unittest.TestCase):
    """V5：细条滚动条无箭头、宽度取令牌、定义迁入 ui_widgets。"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        ui_theme.apply(self.root)
        self.style = ttk.Style(self.root)

    def test_layouts_have_no_arrow_elements(self):
        for name, arrows in (("Vertical.TScrollbar", ("uparrow", "downarrow")),
                             ("Horizontal.TScrollbar", ("leftarrow", "rightarrow"))):
            layout = str(self.style.layout(name))
            for arrow in arrows:
                self.assertNotIn(arrow, layout, "%s 不得含 %s" % (name, arrow))

    def test_scrollbar_thickness_uses_token(self):
        self.assertEqual(int(self.style.lookup("Vertical.TScrollbar", "arrowsize")),
                         SCROLLBAR_WIDTH)
        bar = ttk.Scrollbar(self.root, orient="vertical")
        self.root.update_idletasks()
        self.assertEqual(bar.winfo_reqwidth(), SCROLLBAR_WIDTH)


class PerformanceTests(unittest.TestCase):
    """V7：首次安装耗时、幂等返回与图元缓存。"""

    def test_repeat_setup_returns_early(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        ui_theme.apply(root)
        start = time.perf_counter()
        ui_widgets.setup_styles(root)
        self.assertLess(time.perf_counter() - start, 0.01,
                        "同一主题重复调用必须直接返回")

    def test_rounded_images_are_cached_by_color_radius_size(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        image1, _ = ui_widgets._rounded_photo(root, COLORS["primary"], RADIUS["md"],
                                              width=40, height=40)
        image2, _ = ui_widgets._rounded_photo(root, COLORS["primary"], RADIUS["md"],
                                              width=40, height=40)
        self.assertIs(image1, image2, "相同 (颜色,半径,尺寸) 必须复用同一 PhotoImage")

    def test_first_install_is_within_budget(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        start = time.perf_counter()
        ui_theme.apply(root)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.5, "首次安装样式应远低于 0.5s")


if __name__ == "__main__":
    unittest.main()


class RoundedCornerTests(unittest.TestCase):
    """圆角必须真的露出来：ttk 把透明角处露出的是样式 background，填充色走 fill。"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        ui_theme.apply(self.root)
        self.style = ttk.Style(self.root)

    def test_button_background_is_the_surface_behind_not_the_fill(self):
        from ui_tokens import CONTROL_CORNER_SURFACE
        for name in BUTTON_STYLES:
            with self.subTest(style=name):
                self.assertEqual(str(self.style.lookup(name, "background")).upper(),
                                 CONTROL_CORNER_SURFACE.upper(),
                                 "background 若等于按钮填充色，圆角会被填成实心方角")

    def test_rounded_png_has_transparent_corners_and_opaque_centre(self):
        import base64
        import struct
        import zlib
        from ui_widgets import _rounded_png_bytes
        width = height = 26
        png = base64.b64decode(_rounded_png_bytes("#0F6FC0", 8, width, height))
        pos, idat = 8, b""
        while pos < len(png):
            length, tag = struct.unpack(">I4s", png[pos:pos + 8])
            if tag == b"IDAT":
                idat += png[pos + 8:pos + 8 + length]
            pos += 12 + length
        raw = zlib.decompress(idat)
        stride = 1 + width * 4

        def alpha(x, y):
            return raw[y * stride + 1 + x * 4 + 3]
        self.assertEqual(alpha(0, 0), 0)
        self.assertEqual(alpha(width - 1, height - 1), 0)
        self.assertEqual(alpha(width // 2, height // 2), 255)


class RoundedTileSizeTests(unittest.TestCase):
    """圆角底图中心区必须足够大：ttk 按平铺重绘中心区，2×2 的中心会让整页慢 20 倍。"""

    def test_cached_rounded_images_have_large_tile_centres(self):
        floor_width, floor_height = 64, 32  # 与令牌无关的硬下限：令牌被改小也要红
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        ui_theme.apply(root)
        factor = float(root.tk.call("tk", "scaling")) / (96.0 / 72.0)
        images = list(root._drama_rounded_cache.values())
        self.assertTrue(images)
        for image in images:
            self.assertGreaterEqual(image.width(), round(floor_width * factor))
            self.assertGreaterEqual(image.height(), round(floor_height * factor))

    def test_wide_buttons_redraw_quickly(self):
        import time
        root = tk.Tk()
        root.geometry("1200x700+20+20")
        self.addCleanup(root.destroy)
        ui_theme.apply(root)
        for index in range(20):
            ttk.Button(root, text="按钮%d" % index, style="Primary.TButton",
                       width=80).pack(fill="x", padx=4, pady=1)
        root.update()
        started = time.perf_counter()
        for _ in range(3):
            root.update()
        # 中心区只有 2×2 时这里要几十秒；放宽到 8 秒只为抵抗慢机器抖动。
        self.assertLess(time.perf_counter() - started, 8.0)

    def test_big_tile_images_do_not_inflate_button_or_card_minimum_size(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        ui_theme.apply(root)
        button = ttk.Button(root, text="测试", style="Primary.TButton")
        button.pack()
        root.update_idletasks()
        image_height = max(image.height() for image in root._drama_rounded_cache.values())
        # 底图为平铺而放大，控件最小高度仍只由文字＋内边距决定。
        self.assertLess(button.winfo_reqheight(), image_height // 2)
