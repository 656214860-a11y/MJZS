"""由 design_tokens.md 代码化的 UI 视觉 token。"""

COLORS = {
    "background_primary": "#F7F8FA",
    "background_card": "#FFFFFF",
    "border_default": "#E5E7EB",
    "text_primary": "#1F2937",
    # 文字层级对比度（白底）：primary 14.7、secondary 7.6、muted 4.8，均达到 4.5:1；
    # 禁用态不在此列，另用 disabled_text。
    "text_secondary": "#4B5563",
    "text_muted": "#6B7280",
    "primary": "#2563EB",
    "primary_subtle": "#EFF6FF",
    "danger": "#DC2626",
    "success": "#16A34A",
    "warning": "#D97706",
    # R1428 统一调色板：主题与业务页的派生色一律在此登记，不再各写 hex。
    "text_heading": "#374151",
    "primary_hover": "#1D4ED8",
    "primary_pressed": "#1E40AF",
    "progress": "#2563EB",
    "secondary_bg": "#DBEAFE",
    "secondary_hover": "#BFDBFE",
    "secondary_pressed": "#93C5FD",
    "secondary_text": "#1E40AF",
    "disabled_bg": "#F3F4F6",
    "disabled_text": "#9CA3AF",
    "border_strong": "#D1D5DB",
    "header_bg": "#F3F4F6",
    "code_background": "#F3F4F6",
    "trough": "#E5E7EB",
    "selection_bg": "#DBEAFE",
    "selection_text": "#1E3A8A",
    "selection_border": "#93C5FD",
    "success_text": "#15803D",
    "success_subtle": "#DCFCE7",
    "warning_text": "#B45309",
    "focus": "#2563EB",
    "danger_hover": "#B91C1C",
    "danger_text": "#991B1B",
    "danger_subtle": "#FEF2F2",
    "row_done_bg": "#F0FDF4",
}

SPACING = {"none": 0, "xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32}
RADIUS = {"sm": 4, "md": 8, "lg": 12}
# 紧凑桌面密度：按钮、输入框、下拉框的视觉高度与最小点击区都是 32px。
CONTROL_HEIGHT = SPACING["2xl"]
CONTROL_HIT_MIN = SPACING["2xl"]
# Tk 没有控件高度属性，只能由「字体行高 + 上下内边距 + 边框」凑出 32px（测试容忍 ±2）。
# 10pt 微软雅黑 UI 在 100% DPI 下 linespace=19px；单行输入用 6px 上下内边距：
# 19 + 2×6 + 2×1 边框 = 33px。6 = xs(4) + xs//2，仍由 4px 刻度派生，不手写魔法值。
# 按钮沿用既有 (space.md, space.xs) 内边距，19 + 2×4 + 主题边框/焦点占位 6 = 33px。
CONTROL_PADDING_Y = SPACING["xs"] + SPACING["xs"] // 2
FONTS = {
    "pet_body": ("Microsoft YaHei UI", 9),
    "pet_hint": ("Microsoft YaHei UI", 8),
    # 设置页的原生 ttk 文本默认是 Microsoft YaHei UI 10；统一组件若另用
    # Microsoft YaHei 12，就会让按钮／说明／下拉框在同一表单行看起来忽大忽小。
    # 正文、短说明和下拉展开项共用这一档；标题仅用字重和尺寸表达层级。
    "title": ("Microsoft YaHei UI", 14, "bold"),
    "body": ("Microsoft YaHei UI", 10),
    "body_bold": ("Microsoft YaHei UI", 10, "bold"),
    "caption": ("Microsoft YaHei UI", 10),
    "numeric": ("Consolas", 10),
    "code": ("Consolas", 10),
    "hint": ("Microsoft YaHei UI", 9, "italic"),
    "heading_1": ("Microsoft YaHei UI", 16, "bold"),
    "heading_2": ("Microsoft YaHei UI", 14, "bold"),
    "heading_3": ("Microsoft YaHei UI", 12, "bold"),
    "heading_4": ("Microsoft YaHei UI", 11, "bold"),
}

# 阶段配置「技能说明」栏的布局规格：目录宽度按显示宽度自适应，正文高度由页面按紧凑档选用。
NOTE_LIST_MIN_WIDTH = 12
NOTE_LIST_MAX_WIDTH = 28
NOTE_HEIGHT_COMPACT = 8
NOTE_HEIGHT_REGULAR = 16
NOTE_PADDING_X = SPACING["md"]
NOTE_PADDING_Y = SPACING["sm"]

# 「剧本内容」阅读区：正文、行距、段距与高亮阈值只在这里定义。
SCRIPT_VIEW_FONT = FONTS["body"]
SCRIPT_VIEW_MAX_CHARS = 200_000
SCRIPT_VIEW_LINE_SPACING = SPACING["xs"] // 2
SCRIPT_VIEW_PARAGRAPH_SPACING = SPACING["xs"] // 2
SCRIPT_VIEW_PADDING = (SPACING["lg"], SPACING["md"])
SCRIPT_VIEW_LIST_INDENT = SPACING["lg"]
SCRIPT_VIEW_QUOTE_INDENT = SPACING["md"]

PET_CLOUD_AUTO_CLOSE_MS = 10000

# TCombobox 的默认规格只在这里定义；页面不得另写颜色、字体或内边距。
COMBOBOX_WIDTH = 15
COMBOBOX_POPDOWN_HEIGHT = 12
COMBOBOX_MAX_WIDTH = 28
COMBOBOX_FONT = FONTS["body"]
COMBOBOX_PADDING = (SPACING["sm"], SPACING["xs"])
# SelectBox 的统一控件样式把垂直内边距加到 CONTROL_PADDING_Y，使下拉框与
# TEntry／TSpinbox 同高（Tk 的 TCombobox 高度只由 padding 决定）。
COMBOBOX_CONTROL_PADDING = (COMBOBOX_PADDING[0], CONTROL_PADDING_Y)
COMBOBOX_FIELD_BACKGROUND = COLORS["background_card"]
COMBOBOX_FOREGROUND = COLORS["text_primary"]
COMBOBOX_ARROW_COLOR = COLORS["text_secondary"]

# 表单标签列宽（字符数）：总控／厂商／制作锁等相邻表单行的标签列共用同一基准，保证纵向对齐。
FORM_LABEL_WIDTH = 10

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
# 按钮常态不画可见边框：1px 的 solid 边框用按钮自身底色当边框色，只有键盘焦点
# 状态把它映射为 color.focus。这样既保持扁平观感，又保留键盘焦点环。
BUTTON_BORDER_WIDTH = 1

# 弹窗视觉规格只由 ui_widgets 的 BaseDialog 系列消费；业务页不得另行设置标题、内容区或按钮区样式。
DIALOG_TITLE_FONT = FONTS["title"]
DIALOG_CONTENT_PADDING = SPACING["lg"]
DIALOG_ACTION_HEIGHT = SPACING["xl"]
DIALOG_ACTION_GAP = SPACING["sm"]
# 弹窗最小尺寸：至少并排放下两个 96px 按钮＋12px 间距＋两侧 16px 留白（≈236→240），
# 高度至少容下标题、两行说明和底部动作区（≈160）。低于此值内容必被裁切，
# 因此定位时只允许缩到这两个下限，不再降到 1×1。
DIALOG_MIN_WIDTH = 240
DIALOG_MIN_HEIGHT = 160

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
# 长说明（如会话摘要）折行显示，避免单行浮层伸出屏幕。
TOOLTIP_WRAPLENGTH = 480

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
TABLE_COMPACT_HEADER_PADDING = (SPACING["sm"], SPACING["xs"] // 4)
SCRIPT_ACTION_WIDTH = 0  # 依文字请求宽度，长中文按钮不得裁字。
DESKTOP_LAYOUT = {
    # 产品裁决：主窗口默认 1280×800、最小 800×600；屏幕可用区更小时按下面
    # 的边距收缩（ui_theme.main_window_size），不改变最小值。
    'default_width': 1280, 'default_height': 800,
    'window_margin_x': SPACING['xl'], 'window_margin_y': SPACING['xl'] * 2,
    'min_width': 800, 'min_height': 600,
    'sidebar_width': 154, 'sidebar_padding': 6, 'row_gap': 1,
    'compact_below': 690, 'project_min_rows': 3,
    'project_button_padding': (SPACING['sm'], SPACING['none']),
    'body_padding': (14, SPACING['sm'], 14, SPACING['sm']),
    'title_inset': SPACING['xs'], 'gear_gap': SPACING['xs'],
    'slogan_gap': SPACING['md'], 'slogan_font': FONTS['pet_body'],
    'project_label_gap': SPACING['sm'], 'pet_clearance': SPACING['xs'],
    # 主窗口拖动：停止拖动后等这么久没有新尺寸才整页重排一次（约 8 帧，远长于
    # Windows 拖动时 WM_SIZE 的间隔，又不至于松手后明显停顿）。
    'resize_quiet_ms': 128,
    # 外框可调整区的命中宽度；同时是 Tk 数窗口尺寸时外框到工作区的内缩。
    'resize_edge_px': 4,
}
# 阶段配置弹窗与制作锁流式布局的规格：最小窗口尺寸、标签与下拉框间距、行间距、
# 行尾允许空白与标签旧契约宽度。SP 批次把下拉框改成按行填满的 FlowFields，这些
# 间距原先散落在 skill_panel.py / production_lock_fields.py 里临时挑 SPACING 档位，
# 现统一在这里取值，值保持不变。
STAGE_PANEL_LAYOUT = {
    # 最小窗口 560×430；屏幕可用区更小时按可用区收缩，不让窗口超出屏幕。
    'min_width': 560, 'min_height': 430,
    # 标签与下拉框／字段之间的水平间距（FlowFields.gap 与 label-entry padx）。
    'field_gap': SPACING['xs'],
    # FlowFields 换行后的行间距。
    'row_gap': SPACING['xs'],
    # 行尾允许空白：行未填满时允许的尾部空白容差（真 Tk 几何断言据此判定「填满」）。
    'row_end_tolerance': SPACING['md'],
    # CompactLabel 保留的旧 width=10 契约，真实排版按文字宽度请求。
    'label_width': 10,
}
# 剧本准备文件列表：比正文小一档，一屏多放几个文件名，9 号雅黑仍清晰。
SCRIPT_FILE_FONT = ("Microsoft YaHei UI", 9)
SCRIPT_ACTION_PADDING = (SPACING["md"] // 2, SPACING["xs"])

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

# 启动画面：深色底＋播放键＋细进度条，整块盖住主窗口直到加载完成。
SPLASH_BACKGROUND = "#0F172A"
SPLASH_FILM = "#1E293B"
SPLASH_ACCENT = "#38BDF8"
SPLASH_ACCENT_ALT = "#A78BFA"
SPLASH_TITLE = "#F8FAFC"
SPLASH_SUBTITLE = "#94A3B8"
SPLASH_TITLE_FONT = ("Microsoft YaHei UI", 22, "bold")
SPLASH_SUBTITLE_FONT = ("Microsoft YaHei UI", 10)
SPLASH_BAR_HALF = 160
SPLASH_FRAME_MS = 33
SPLASH_POLL_MS = 30
SPLASH_FINISH_MS = 160
SPLASH_CREEP = 0.12

# 小图标按钮：用系统自带的线框图标字体，不用彩色表情——首次绘制表情要加载
# Segoe UI Emoji，实测单颗按钮卡住主线程约 0.4 秒（R1415）。
ICON_FONT = ("Segoe MDL2 Assets", 11)
ICON_FOLDER = "\uE8B7"
ICON_DELETE = "\uE74D"

# 主窗口三虎：绘图保留原坐标系，显示尺寸和命中区域共用这组紧凑布局值。
PET_LAYOUT = {
    "source_size": 64,
    "avatar_size": 48,
    "paw_size": 16,
    "paw_gap": 2,
    "paw_gap_y": 2,
    "paw_arc": 2,
    "top": SPACING["none"],
    "right_gap": SPACING["xs"],
    "caption_right": SPACING["sm"],
    "caption_width": 64,
    "caption_height": 20,
    "header_gap": SPACING["sm"],
}
