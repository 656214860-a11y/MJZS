"""剧本准备页输入框样式（仿 Claude Code 桌面版），由 ui_widgets.setup_styles 调用。"""
from ui.ui_rounded import rounded_photo
from ui_tokens import COLORS, FONTS, ICON_FONT, ICON_FONT_SMALL, RADIUS, ROUND_TILE_BUTTON, SPACING


def install_composer_styles(style, root, configure_button):
    """剧本准备页输入框（仿 Claude Code 桌面版）：框内底色、附件卡片、框内图标按钮。

    框内控件都画在卡片白底上，所以圆角按钮透出的表面色要改成卡片底色，否则四角是页面灰。
    """
    card = COLORS["background_card"]
    style.configure("Composer.TFrame", background=card)
    style.configure("Composer.TLabel", background=card, foreground=COLORS["text_primary"])
    style.configure("Composer.Muted.TLabel", background=card, foreground=COLORS["text_secondary"])
    style.configure("Composer.Chip.Icon.TLabel", background=card, font=ICON_FONT,
                    foreground=COLORS["text_secondary"])
    style.configure("Composer.Chip.Close.TLabel", background=card, font=ICON_FONT_SMALL,
                    foreground=COLORS["text_muted"], padding=SPACING["xs"])
    style.map("Composer.Chip.Close.TLabel",
              foreground=[("active", COLORS["danger"])],
              background=[("active", COLORS["surface_hover"])])
    factor = float(root.tk.call("tk", "scaling")) / (96.0 / 72.0)
    pr = max(1, round(RADIUS["md"] * factor))
    tile_w, tile_h = ROUND_TILE_BUTTON
    for name, border, width in (("Tokens.Chip.TFrame", COLORS["border_default"], 1),
                                ("Tokens.Chip.Selected.TFrame", COLORS["primary"], 2)):
        image, _ = rounded_photo(root, card, RADIUS["md"],
                                  width=RADIUS["md"] * 2 + tile_w, height=RADIUS["md"] * 2 + tile_h,
                                  border=border, border_width=width)
        element = "Drama." + name.replace(".", "_")
        if element not in style.element_names():
            style.element_create(element, "image", image, border=(pr, pr, pr, pr),
                                 padding=(0, 0, 0, 0), width=1, height=1, sticky="nsew")
        style.layout(name, [(element, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew"})]})])
        style.configure(name, background=card)  # 内边距写在卡片控件上（见 desktop_idea_chat），样式里的不生效
    configure_button(style, "Tokens.Composer.Icon.TButton", font=ICON_FONT,
                      background=card, foreground=COLORS["text_secondary"],
                      active_background=COLORS["surface_hover"],
                      active_foreground=COLORS["text_primary"],
                      pressed_background=COLORS["surface_pressed"],
                      padding=(SPACING["sm"], SPACING["xs"]))
    # 听写中的麦克风沿用主色高亮，不随发送键改成圆环。
    configure_button(style, "Tokens.Composer.Listening.TButton", font=ICON_FONT,
                      background=COLORS["primary"], foreground=card,
                      active_background=COLORS["primary_hover"], active_foreground=card,
                      pressed_background=COLORS["primary_pressed"],
                      padding=(SPACING["sm"], SPACING["xs"]))
    # 方形图元不做九宫格拉伸：圆角半径等于边长的一半。
    size = SPACING["2xl"]
    radius = size // 2
    ring = {}
    for state, border in (("normal", COLORS["border_input_hover"]),
                          ("active", COLORS["primary"]),
                          ("disabled", COLORS["disabled_text"]),
                          ("focus", COLORS["focus"])):
        ring[state], _ = rounded_photo(root, card, radius, size, size,
                                       border=border, border_width=1)
    element = "Drama.Composer.SendRing"
    if element not in style.element_names():
        style.element_create(element, "image", ring["normal"],
                             ("disabled", ring["disabled"]), ("active", ring["active"]),
                             ("focus", ring["focus"]), sticky="")
    name = "Tokens.Composer.Send.TButton"
    style.layout(name, [(element, {"sticky": "", "children": [
        ("Button.focus", {"sticky": "nswe", "children": [
            ("Button.label", {"sticky": ""})]})]})])
    style.configure(name, font=ICON_FONT, padding=0, width=0, background=card,
                    foreground=COLORS["border_input_hover"], focuscolor=COLORS["focus"])
    style.map(name, foreground=[("disabled", COLORS["disabled_text"]),
                                ("active", COLORS["primary"]),
                                ("focus", COLORS["focus"])])
    # 模型选择器触发钮（R2964）：卡片底同色＝无外框文字钮，悬停才透出圆角底。
    configure_button(style, "Tokens.Composer.Model.TButton", font=FONTS["body"],
                      background=card, foreground=COLORS["text_secondary"],
                      active_background=COLORS["surface_hover"],
                      active_foreground=COLORS["text_primary"],
                      pressed_background=COLORS["surface_pressed"],
                      padding=(SPACING["xs"], SPACING["xs"]))
    for name in ("Tokens.Composer.Icon.TButton", "Tokens.Composer.Send.TButton",
                 "Tokens.Composer.Model.TButton"):
        style.configure(name, background=card)
