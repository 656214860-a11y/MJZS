"""由 design_tokens.md 代码化的 UI 视觉 token。"""

COLORS = {
    "background_primary": "#F7F8FA",
    "background_card": "#FFFFFF",
    "border_default": "#E5E7EB",
    "text_primary": "#1F2937",
    "text_secondary": "#6B7280",
    "text_muted": "#9CA3AF",
    "primary": "#2563EB",
    "primary_subtle": "#EFF6FF",
    "danger": "#DC2626",
    "success": "#16A34A",
    "warning": "#D97706",
}

SPACING = {"none": 0, "xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32}
RADIUS = {"sm": 4, "md": 8, "lg": 12}
FONTS = {
    "title": ("Microsoft YaHei", 14, "bold"),
    "body": ("Microsoft YaHei", 12),
    "caption": ("Microsoft YaHei", 10),
    "numeric": ("Consolas", 12),
}

# TCombobox 的默认规格只在这里定义；页面不得另写颜色、字体或内边距。
COMBOBOX_WIDTH = 15
COMBOBOX_FONT = FONTS["body"]
COMBOBOX_PADDING = (SPACING["sm"], SPACING["xs"])
COMBOBOX_FIELD_BACKGROUND = COLORS["background_card"]
COMBOBOX_FOREGROUND = COLORS["text_primary"]
COMBOBOX_ARROW_COLOR = COLORS["text_secondary"]

# 弹窗视觉规格只由 ui_widgets 的 BaseDialog 系列消费；业务页不得另行设置标题、内容区或按钮区样式。
DIALOG_TITLE_FONT = FONTS["title"]
DIALOG_CONTENT_PADDING = SPACING["lg"]
DIALOG_ACTION_HEIGHT = SPACING["xl"]
DIALOG_ACTION_GAP = SPACING["sm"]

# 三类用户可见文字只在 ui_widgets 的文字组件中消费；页面不再各自拼字体、颜色和折行规格。
TEXT_HINT = {
    "font": FONTS["caption"],
    "foreground": COLORS["text_secondary"],
    "wraplength": 240,
    "linespace": SPACING["xs"],
    "anchor": "w",
    "justify": "left",
    "padding": (SPACING["none"], SPACING["xs"]),
    "max_chars": 20,
}
TEXT_DESC = {
    "font": FONTS["body"],
    "foreground": COLORS["text_secondary"],
    "wraplength": 560,
    "linespace": SPACING["sm"],
    "anchor": "w",
    "justify": "left",
    "padding": (SPACING["none"], SPACING["sm"]),
    "max_chars": 60,
}
TEXT_PROGRESS = {
    "font": FONTS["body"],
    "foreground": COLORS["primary"],
    "wraplength": 480,
    "linespace": SPACING["xs"],
    "anchor": "w",
    "justify": "left",
    "padding": (SPACING["sm"], SPACING["xs"]),
    "max_chars": 40,
}
