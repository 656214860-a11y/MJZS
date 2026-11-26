"""统一紧凑关闭 × 按钮（UX-CLOSE-X）：L4 组件工厂与样式装配。

全应用 5 处关闭 ×（S02 结构剧本编辑器、S03 初步分镜编辑器、S01 模型目录条、
状态栏消息历史浮窗、三虎云朵）共用本模块的圆角图元、字号令牌与悬停红底白×契约。
"""
from __future__ import annotations

from ui.ui_rounded import rounded_layout, rounded_photo
from ui.ui_tooltip import Tooltip
from ui_tokens import (
    CLOSE_BUTTON_COMPACT_ACTIVE_STYLE,
    CLOSE_BUTTON_COMPACT_FONT,
    CLOSE_BUTTON_COMPACT_PADDING,
    CLOSE_BUTTON_COMPACT_STYLE,
    CLOSE_BUTTON_FONT,
    CLOSE_BUTTON_MARK,
    CLOSE_BUTTON_PADDING,
    CLOSE_BUTTON_RADIUS,
    CLOSE_BUTTON_STYLE,
    COLORS,
    ROUND_TILE_BUTTON,
    current_theme,
)


def _install_close_style(style, root, name, *, surface, font, padding):
    """为单个关闭按钮样式生成四态圆角图元并绑定中性常态／红底白×悬停映射。"""
    tile_w, tile_h = ROUND_TILE_BUTTON
    radius = CLOSE_BUTTON_RADIUS
    width = radius * 2 + tile_w
    height = radius * 2 + tile_h
    states = (
        ("normal", surface),
        ("active", COLORS["danger"]),
        ("pressed", COLORS["danger_pressed"]),
        ("disabled", COLORS["disabled_bg"]),
    )
    images = {}
    for state, color in states:
        images[state], pr = rounded_photo(root, color, radius, width=width, height=height)
    element = "Drama.Close." + name.replace(".", "_") + "." + current_theme()
    if element not in style.element_names():
        style.element_create(
            element, "image", images["normal"],
            ("disabled", images["disabled"]),
            ("pressed", images["pressed"]),
            ("active", images["active"]),
            border=(pr, pr, pr, pr),
            padding=(0, 0, 0, 0),
            width=1, height=1, sticky="nsew",
        )
    rounded_layout(style, name, element)
    style.configure(
        name,
        font=font,
        padding=padding,
        background=surface,
        fill=surface,
        foreground=COLORS["text_secondary"],
        focuscolor=COLORS["focus"],
        anchor="center",
        width=0,
    )
    style.map(
        name,
        fill=[
            ("pressed", COLORS["danger_pressed"]),
            ("active", COLORS["danger"]),
            ("disabled", COLORS["disabled_bg"]),
        ],
        foreground=[
            ("pressed", COLORS["on_accent"]),
            ("active", COLORS["on_accent"]),
            ("disabled", COLORS["disabled_text"]),
        ],
    )
    # 独立登记四态规格（不写入 ui_rounded.button_specs），保证 ui_hover_fade 跳过渐变、
    # 鼠标移入瞬间切至实心红底白×，避免白底→红底第 0 帧闪白字。
    specs = getattr(root, "_drama_close_button_specs", None)
    if specs is None:
        specs = root._drama_close_button_specs = {}
    specs[name] = {
        "colors": dict(states),
        "images": images,
        "radius": radius,
        "surface": surface,
    }


def configure_close_button_styles(style, root):
    """由 ui_widgets.setup_styles(root) 调用：按当前主题装配全部 Tokens.Close.* 样式。"""
    card = COLORS["background_card"]
    _install_close_style(
        style, root, CLOSE_BUTTON_STYLE,
        surface=card, font=CLOSE_BUTTON_FONT, padding=CLOSE_BUTTON_PADDING,
    )
    _install_close_style(
        style, root, CLOSE_BUTTON_COMPACT_STYLE,
        surface=card, font=CLOSE_BUTTON_COMPACT_FONT, padding=CLOSE_BUTTON_COMPACT_PADDING,
    )
    _install_close_style(
        style, root, CLOSE_BUTTON_COMPACT_ACTIVE_STYLE,
        surface=COLORS["primary_subtle"],
        font=CLOSE_BUTTON_COMPACT_FONT,
        padding=CLOSE_BUTTON_COMPACT_PADDING,
    )


def make_close_button_class(base_button):
    """基于 SecondaryButton 构造 CloseButton，避免 ui_widgets 循环导入并守住按钮边界门禁。"""

    class CloseButton(base_button):
        """全应用统一紧凑关闭 × 按钮（支持标准档与 S01 极窄标签紧凑档）。"""

        def __init__(self, master=None, *, compact=False, active_surface=False,
                     tooltip=None, **kwargs):
            if compact:
                default_style = (CLOSE_BUTTON_COMPACT_ACTIVE_STYLE if active_surface
                                 else CLOSE_BUTTON_COMPACT_STYLE)
            else:
                default_style = CLOSE_BUTTON_STYLE
            kwargs.setdefault("text", CLOSE_BUTTON_MARK)
            kwargs.setdefault("style", default_style)
            kwargs.setdefault("width", 0)
            kwargs.setdefault("takefocus", True)
            kwargs.setdefault("cursor", "hand2")
            super().__init__(master, **kwargs)
            for sequence in ("<Return>", "<space>"):
                self.bind(sequence, self._activate_from_key, add="+")
            self._close_tooltip = Tooltip(self, tooltip) if tooltip else None

        def _activate_from_key(self, _event=None):
            self.invoke()
            return "break"

    CloseButton.__name__ = "CloseButton"
    CloseButton.__qualname__ = "CloseButton"
    CloseButton.__module__ = __name__
    globals()["CloseButton"] = CloseButton
    return CloseButton
