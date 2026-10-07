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
    # 设置页的原生 ttk 文本默认是 Microsoft YaHei UI 10；统一组件若另用
    # Microsoft YaHei 12，就会让按钮／说明／下拉框在同一表单行看起来忽大忽小。
    # 正文、短说明和下拉展开项共用这一档；标题仅用字重和尺寸表达层级。
    "title": ("Microsoft YaHei UI", 14, "bold"),
    "body": ("Microsoft YaHei UI", 10),
    "caption": ("Microsoft YaHei UI", 10),
    "numeric": ("Consolas", 10),
}

# TCombobox 的默认规格只在这里定义；页面不得另写颜色、字体或内边距。
COMBOBOX_WIDTH = 15
COMBOBOX_POPDOWN_HEIGHT = 12
COMBOBOX_MAX_WIDTH = 28
COMBOBOX_FONT = FONTS["body"]
COMBOBOX_PADDING = (SPACING["sm"], SPACING["xs"])
COMBOBOX_FIELD_BACKGROUND = COLORS["background_card"]
COMBOBOX_FOREGROUND = COLORS["text_primary"]
COMBOBOX_ARROW_COLOR = COLORS["text_secondary"]

# 输入框的视觉与状态只由 ui_widgets.LineInput / TextArea 消费；页面只传内容、
# 宽高与领域校验，不能重新拼字体、颜色、边框或占位态。
INPUT_FONT = FONTS["body"]
INPUT_FOREGROUND = COLORS["text_primary"]
INPUT_PLACEHOLDER_FOREGROUND = COLORS["text_secondary"]
INPUT_BACKGROUND = COLORS["background_card"]
INPUT_BORDER = COLORS["border_default"]
INPUT_ERROR_BORDER = COLORS["danger"]
INPUT_PADDING_X = SPACING["md"]
INPUT_PADDING_Y = SPACING["sm"]
INPUT_BORDER_WIDTH = 1

# 弹窗视觉规格只由 ui_widgets 的 BaseDialog 系列消费；业务页不得另行设置标题、内容区或按钮区样式。
DIALOG_TITLE_FONT = FONTS["title"]
DIALOG_CONTENT_PADDING = SPACING["lg"]
DIALOG_ACTION_HEIGHT = SPACING["xl"]
DIALOG_ACTION_GAP = SPACING["sm"]

# Tooltip 的出现节奏和视觉只由 ui_widgets.Tooltip 消费；页面只提供说明文本，
# 不得各自创建无边框窗口或复制 Enter/Leave 的延迟与销毁逻辑。
TOOLTIP_DELAY_MS = 400
TOOLTIP_OFFSET = SPACING["sm"]
TOOLTIP_PADDING = (SPACING["sm"], SPACING["xs"])
TOOLTIP_FONT = FONTS["caption"]
TOOLTIP_FOREGROUND = COLORS["text_primary"]
TOOLTIP_BACKGROUND = COLORS["background_card"]
TOOLTIP_BORDER = COLORS["border_default"]
TOOLTIP_BORDER_WIDTH = 1

# TScrollbar 的视觉只由 ui_theme.apply() 消费；页面只建立标准 ttk.Scrollbar。
SCROLLBAR_THUMB = "#C6D2E1"
SCROLLBAR_THUMB_ACTIVE = "#9FB4CC"
SCROLLBAR_TROUGH = COLORS["background_primary"]
SCROLLBAR_ARROW = "#52677F"
SCROLLBAR_BORDER_WIDTH = 0

# 表格视觉规格只由 ui_widgets.DataTable 消费；业务页只给列定义与数据，
# 不得各自复制 Treeview 样式、滚动条或空态。
TABLE_HEADER_FONT = FONTS["body"]
TABLE_ROW_FONT = FONTS["body"]
TABLE_ROW_HEIGHT = SPACING["xl"]
TABLE_EMPTY_PADDING = SPACING["lg"]

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
