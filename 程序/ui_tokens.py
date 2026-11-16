"""由 design_tokens.md 代码化的 UI 视觉 token。"""

COLORS = {
    # 2026-10-21 现代色阶：页面底、卡片底、悬停面。
    "background_primary": "#F7F9F9",
    "background_card": "#FFFFFF",
    "surface_hover": "#EFF3F4",
    "surface_pressed": "#DFE6E9",
    # 分隔线两档：弱分隔线（卡片/容器/tooltip 描边）与输入框描边。
    # 原 #EFF3F4 画在 background_primary 上对比度仅约 1.06:1，卡片边线几乎看不见
    "border_default": "#DCE3E7",
    "row_completed": "#EFF3F4",          # 表格「已完成」行底色（原借用 border_default）
    "border_input": "#CFD9DE",
    "border_input_hover": "#A9BAC4",
    # 文字层级：正文/次级/弱化在白底分别为 18.5/6.1/5.3:1，弱化在悬停面 4.75:1，均 ≥4.5:1；
    # 禁用态不在此列，另用 disabled_text。
    "text_primary": "#0F1419",
    "text_secondary": "#536471",
    "text_muted": "#616D76",
    "text_heading": "#0F1419",
    # 主色（X 蓝深档）：与白 5.18:1、与页面底 4.90:1；悬停/按下逐档加深。
    "primary": "#0F6FC0",
    "primary_subtle": "#E8F3FB",
    "primary_hover": "#0C5FA6",
    "primary_pressed": "#0A4F8C",
    "focus": "#0F6FC0",
    # 装饰色（X 蓝）：聚焦环、侧边指示条等非文字用途，对白 3.0:1；不得作按钮底色或文字色。
    "accent": "#1D9BF0",
    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "danger_pressed": "#7F1D1D",
    "danger_text": "#991B1B",
    "danger_subtle": "#FEF2F2",
    # success 由 #16A34A 加深一档，使白字对比度 3.3→5.0（V1 要求实色按钮白字 ≥4.5:1）。
    "success": "#15803D",
    "success_text": "#15803D",
    "success_subtle": "#DCFCE7",
    "warning": "#D97706",
    "warning_text": "#B45309",
    # 旧式次按钮（默认 TButton 族）逐档加深的浅蓝：secondary_hover/pressed 本轮起被实际消费。
    "secondary_bg": "#DBEAFE",
    "secondary_hover": "#BFDBFE",
    "secondary_pressed": "#93C5FD",
    "secondary_text": "#1E40AF",
    "disabled_bg": "#F3F4F6",
    "disabled_text": "#9CA3AF",
    "border_strong": "#D1D5DB",
    "header_bg": "#F7F9F9",
    "code_background": "#F3F4F6",
    "trough": "#EFF3F4",
    "selection_bg": "#E8F3FB",
    "selection_text": "#0A4F8C",
    "selection_border": "#B7D3EC",
    "progress": "#0F6FC0",
    "row_done_bg": "#F0FDF4",
}

SPACING = {"none": 0, "xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32}
RADIUS = {"sm": 4, "md": 8, "lg": 12}
# 文字单位的尺寸刻度（R1885）：控件 width 以字符计、文本区/表格 height 以行计，不是像素。
# 业务页一律从刻度取值；旧值按「就近、平局取大」吸附（取大避免裁字）。
CHAR_WIDTH = {"xs": 4, "sm": 6, "md": 8, "lg": 10, "xl": 12, "2xl": 14, "3xl": 16,
              "field_sm": 48, "field_md": 64, "field_lg": 80}
TEXT_ROWS = {"xs": 2, "sm": 4, "md": 6, "lg": 8, "xl": 10, "2xl": 12, "3xl": 16, "4xl": 20}
# 说明/状态文字折行宽度（像素），80px 一档；旧值向下取档，保证不超出原容器。
WRAPLENGTH = {"sm": 480, "md": 560, "lg": 640, "xl": 720, "2xl": 800, "3xl": 880, "4xl": 960}
# 桌面密度（2026-10-21 密度放松）：按钮、输入框、下拉框的视觉高度与最小点击区 32→36px。
CONTROL_HEIGHT = SPACING["2xl"] + SPACING["xs"]
CONTROL_HIT_MIN = CONTROL_HEIGHT
# Tk 没有控件高度属性，只能由「字体行高 + 上下内边距 + 边框」凑出 36px（测试容忍 ±2）。
# 10pt 微软雅黑 UI 在 100% DPI 下 linespace=19px；单行输入用 8px 上下内边距：
# 19 + 2×8 + 2×1 边框 = 37px（36±2 内）。8 = space.sm，由 4px 刻度派生，不手写魔法值。
# 按钮沿用 CONTROL_PADDING_Y 作垂直内边距，19 + 2×8 + 焦点/圆角占位 ≈ 37px。
CONTROL_PADDING_Y = SPACING["sm"]
# 按钮宽度与间距规则（R1970）：
# - 按钮最小宽度（字符）。clam 的 TButton 默认隐含 -width -11，此前无处声明；显式写出后
#   「不设 width」的短按钮 = 11 字符，同组要自适应文字宽度的按钮传 width=0。
# - 同一行按钮之间默认 sm(8)；图标按钮／紧凑行才用 xs(4)。
BUTTON_MIN_WIDTH = 11
BUTTON_GAP = SPACING["sm"]
BUTTON_GAP_TIGHT = SPACING["xs"]
# 同类按钮的固定字符宽（页面不再各自维护常量）：阶段主操作／阶段配置、编辑栏小按钮、确认弹窗成对按钮。
BUTTON_WIDTH_STAGE = CHAR_WIDTH["3xl"]
BUTTON_WIDTH_EDIT = 7
BUTTON_WIDTH_DIALOG = CHAR_WIDTH["xl"]
# 侧栏导航按钮横向内边距与矮窗口（compact）纵向内边距；fit_sidebar 只经这些令牌改样式。
NAV_PADDING_X = 10
NAV_SUB_PADDING_X = 26
NAV_PADDING_Y_COMPACT = 1
NAV_PADDING_Y = SPACING["xs"]
NAV_ROW_HEIGHT = 24
NAV_ROW_HEIGHT_COMPACT = 20
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
    "hint": ("Microsoft YaHei UI", 9),
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
NOTE_PARAGRAPH_SPACING = SPACING["xs"] // 2

# 「剧本内容」阅读区：正文、行距、段距与高亮阈值只在这里定义。
SCRIPT_VIEW_FONT = FONTS["body"]
# 正文缩放区间（R2641／REQ-S02-36）：下限与 pet_hint 同档，再小无法阅读；
# 上限 32pt 时单屏行数过少，超出后改横向滚动体验更差。
SCRIPT_VIEW_FONT_MIN = 8
SCRIPT_VIEW_FONT_MAX = 32
SCRIPT_VIEW_MAX_CHARS = 200_000
SCRIPT_VIEW_LINE_SPACING = SPACING["xs"] // 2
SCRIPT_VIEW_PARAGRAPH_SPACING = SPACING["xs"] // 2
SCRIPT_VIEW_PADDING = (SPACING["lg"], SPACING["md"])
SCRIPT_VIEW_LIST_INDENT = SPACING["lg"]
SCRIPT_VIEW_QUOTE_INDENT = SPACING["md"]
SCRIPT_DIRECTORY_MIN_WIDTH = SPACING["xl"] * 4
SCRIPT_DIRECTORY_MAX_WIDTH = SCRIPT_DIRECTORY_MIN_WIDTH + SPACING["md"]
SCRIPT_DIRECTORY_COLUMN_PADDING = SPACING["lg"] + SPACING["xs"]
SCRIPT_DIRECTORY_MAX_ROWS = 6
# 行号槽宽（像素）：容下四位行号加两侧边距；行号位数更多时 gutter 按需加宽。
SCRIPT_GUTTER_WIDTH = SPACING["2xl"] + SPACING["sm"]

PET_CLOUD_AUTO_CLOSE_MS = 10000
# R1948：云朵停留按用户操作疏密伸缩——最近 PET_ACTIVITY_WINDOW_SECONDS 秒里一下没动停久一点，
# 动作满 PET_ACTIVITY_BUSY_COUNT 下（连着点按钮、切页）就短暂停留，其余按 PET_CLOUD_AUTO_CLOSE_MS。
PET_CLOUD_IDLE_CLOSE_MS = 15000
PET_CLOUD_BUSY_CLOSE_MS = 5000
PET_ACTIVITY_WINDOW_SECONDS = 20.0
PET_ACTIVITY_BUSY_COUNT = 4
# R1948：用户主动点掉云朵后的安静期逐次加长（PET_DISMISS_WINDOW_SECONDS 内第 1／2／3 次起），尊重「别打扰我」。
PET_DISMISS_MUTE_SECONDS = (30.0, 120.0, 300.0)
PET_DISMISS_WINDOW_SECONDS = 600.0

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
# 只读下拉框当前值为空时显示的占位文字与颜色（只是显示，不写入取值）。
COMBOBOX_PLACEHOLDER = "请选择"
COMBOBOX_PLACEHOLDER_COLOR = COLORS["text_muted"]

# 表单标签列宽（字符数）：总控／厂商／制作锁等相邻表单行的标签列共用同一基准，保证纵向对齐。
FORM_LABEL_WIDTH = 10

# 输入框的视觉与状态只由 ui_widgets.LineInput / TextArea 消费；页面只传内容、
# 宽高与领域校验，不能重新拼字体、颜色、边框或占位态。
INPUT_FONT = FONTS["body"]
INPUT_FOREGROUND = COLORS["text_primary"]
INPUT_PLACEHOLDER_FOREGROUND = COLORS["text_secondary"]
INPUT_BACKGROUND = COLORS["background_card"]
INPUT_BORDER = COLORS["border_input"]
INPUT_BORDER_HOVER = COLORS["border_input_hover"]
INPUT_FOCUS_BORDER = COLORS["primary"]
INPUT_ERROR_BORDER = COLORS["danger"]
INPUT_PADDING_X = SPACING["lg"]
INPUT_PADDING_Y = SPACING["sm"]
INPUT_BORDER_WIDTH = 1
# 按钮圆角底图：半径取 RADIUS['md']，图元按 (颜色, 半径, 尺寸) 缓存；焦点环仍用 color.focus。
BUTTON_RADIUS = RADIUS["md"]
# ttk 把圆角底图透明处露出的是样式的 background：它必须是控件背后的表面色（页面底），
# 不能是控件自身的填充色，否则圆角会被填成实心方角。
CONTROL_CORNER_SURFACE = COLORS["background_primary"]
# 圆角底图中心区（宽, 高，100% 缩放下的像素）：ttk 的 image 元素把中心区按平铺重绘，
# 中心太小会让一个宽控件每次重绘铺几万次（实测整页慢 20 倍）。按钮 128×64 够一个按钮铺 1～2 片，
# 卡片 256×256 够整块卡片只铺个位数；图越大只是内存多几百 KB，生成代价与尺寸几乎无关。
ROUND_TILE_BUTTON = (128, 64)
ROUND_TILE_CARD = (256, 256)
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
# 语音输入：界面每隔这么久取一次后台听写结果。
VOICE_POLL_MS = 150
# 剧本结构页编辑：停止输入这么久后自动保存一次（REQ-S02-35，R2724 恢复自动保存）。
SCRIPT_EDIT_SAVE_DEBOUNCE_MS = 600
TOOLTIP_OFFSET = SPACING["sm"]
TOOLTIP_PADDING = (SPACING["sm"], SPACING["xs"])
TOOLTIP_FONT = FONTS["caption"]
TOOLTIP_FOREGROUND = COLORS["text_primary"]
TOOLTIP_BACKGROUND = COLORS["background_card"]
TOOLTIP_BORDER = COLORS["border_default"]
TOOLTIP_BORDER_WIDTH = 1
# 长说明（如会话摘要）折行显示，避免单行浮层伸出屏幕。
TOOLTIP_WRAPLENGTH = 480

# TScrollbar 的视觉只由 ui_widgets.setup_styles() 消费（从 ui_theme 迁入）；
# 页面只建立标准 ttk.Scrollbar。细条：无箭头，厚度走 arrowsize。
SCROLLBAR_THUMB = "#C4CCD2"
SCROLLBAR_THUMB_ACTIVE = "#A8B3BC"
SCROLLBAR_TROUGH = COLORS["background_primary"]
SCROLLBAR_BORDER_WIDTH = 0
SCROLLBAR_WIDTH = SPACING["sm"]

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
    'sidebar_width': 154, 'sidebar_title_chars': 5, 'login_gate_width': 460, 'sidebar_padding': SPACING['sm'], 'row_gap': 1,
    # 侧栏导航胶囊之间的垂直间距与「我的项目」「导航」两段之间的呼吸距。
    'nav_gap': SPACING['xs'], 'section_gap': SPACING['md'],
    'compact_below': 690, 'project_min_rows': 3,
    'project_button_padding': (SPACING['sm'], SPACING['none']),
    # 页面边距加大一档：内容与窗口边缘、进度条与状态栏之间都留出呼吸感。
    'body_padding': (SPACING['xl'], SPACING['lg'], SPACING['xl'], SPACING['md']),
    'status_gap': (SPACING['sm'], SPACING['md']),
    'title_inset': SPACING['xs'], 'gear_gap': SPACING['xs'],
    'slogan_gap': SPACING['md'], 'slogan_font': FONTS['pet_body'],
    'project_label_gap': SPACING['sm'], 'pet_clearance': SPACING['xs'],
    # 主窗口拖动：停止拖动后等这么久没有新尺寸才整页重排一次（约 8 帧，远长于
    # Windows 拖动时 WM_SIZE 的间隔，又不至于松手后明显停顿）。
    'resize_quiet_ms': 128,
    # 外框可调整区的命中宽度；同时是 Tk 数窗口尺寸时外框到工作区的内缩。
    'resize_edge_px': 4,
}
# 登录闸内文字的换行宽度：闸宽减去卡片左右内边距，长提示不被裁切。
DESKTOP_LAYOUT['login_gate_wrap'] = DESKTOP_LAYOUT['login_gate_width'] - 2 * SPACING['lg']
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
    # 阶段配置页所有下拉框的统一宽度（字符）；选项更长时靠弹出列表自适应展示全名。
    'select_width': 8,
    # 与下拉框同宽的单行文本输入字符数：tk.Text 的 width 语义与 ttk.Combobox 不同，
    # 7 字符 ≈ 下拉框 8 字符的像素宽（Text 的内边距 INPUT_PADDING_X 更宽），保证两者视觉同宽。
    'text_width': 7,
    # 与下拉框同高的文本输入垂直内边距：tk.Text 的 highlightthickness（上下各 1px）使
    # height=1 时比下拉框高 2px，这里比 INPUT_PADDING_Y 少 1px 抵消，保证行高一致。
    'text_pady': SPACING['sm'] - 1,
    # 标签文字统一左对齐，左侧缩进这么多像素（含在标签请求宽度内）。
    'label_indent': SPACING['xs'],
    # 「下拉框 → 下一个标签」之间的间距，比标签与自己下拉框的 field_gap 大，一眼分得出归属。
    'item_gap': SPACING['md'],
}
# 弹窗覆盖主界面的统一比例（方案 B）：弹窗初始尺寸＝主界面 × 该比例，居中覆盖，
# 永不超出主界面；内容兜底与绝对上限各自在弹窗模块里封顶，避免超大屏过度放大。
# R2411 由 0.78 调至 1.0：阶段配置／设置页／模型管理三弹窗尺寸＝主界面，视觉上像
# 切换页面（用户拍板），居中覆盖主界面。
OVERLAY_RATIO = 1.0
# 剧本准备文件列表：比正文小一档，一屏多放几个文件名，9 号雅黑仍清晰。
SCRIPT_FILE_FONT = ("Microsoft YaHei UI", 9)
SCRIPT_FILE_MAX_ROWS = 6  # 每类文件表最多同时露出的行数，再多靠滚动条
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
SPLASH_MAX_SECONDS = 2.5   # 画面最长盖这么久，超时强制揭开（页面接着在原位建完）

# 小图标按钮：用系统自带的线框图标字体，不用彩色表情——首次绘制表情要加载
# Segoe UI Emoji，实测单颗按钮卡住主线程约 0.4 秒（R1415）。
ICON_FONT = ("Segoe MDL2 Assets", 11)
ICON_FOLDER = "\uE8B7"
ICON_DELETE = "\uE74D"
# \u5267\u672C\u51C6\u5907\u9875\u8F93\u5165\u6846\uFF08\u4EFF Claude Code \u684C\u9762\u7248\uFF09\uFF1A\u6846\u5185\u300C+\u300D\u4E0A\u4F20\u3001\u53D1\u9001\uFF0F\u7EC8\u6B62\u5408\u4E00\u3001\u9644\u4EF6\u5361\u7247\u53F3\u4E0A\u89D2 \u00D7\u3002
ICON_ADD = "\uE710"
ICON_SEND = "\uE74A"
ICON_STOP = "\uE71A"
ICON_CLOSE = "\uE711"
ICON_DOCUMENT = "\uE8A5"
# 对话消息悬停图标与框内麦克风（REQ-S01-66／67）。
ICON_COPY = "\uE8C8"
ICON_REWIND = "\uE7A7"
ICON_MICROPHONE = "\uE720"
ICON_FONT_SMALL = ("Segoe MDL2 Assets", 7)
# 技能图标（共享输入框左下角，Devin 风格星形入口；U+2726 走 Segoe UI Symbol，非彩色表情）。
ICON_SKILL = "\u2726"
# 项目文件栏折叠/展开（剧本准备页，R2942）：收起时指向左、展开时指向右。
ICON_CHEVRON_LEFT = "\uE76B"
ICON_CHEVRON_RIGHT = "\uE76C"

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

# 表格行悬停：行背景由底色淡入到悬停面（STEPS 帧、每帧 FRAME_MS 毫秒），只用 Treeview 标签实现。
ROW_HOVER_TAG = "row_hover"
ROW_HOVER_STEPS = 4
ROW_HOVER_FRAME_MS = 16

# 加载动画：Canvas 画一段旋转圆弧（弧长 EXTENT 度、每帧转 STEP 度）；颜色取主色。
SPINNER_SIZE = SPACING["lg"]
SPINNER_WIDTH = SPACING["xs"] // 2
SPINNER_EXTENT = 100
SPINNER_STEP = 30
SPINNER_FRAME_MS = 50
SPINNER_MARGIN = SPACING["md"]

# 空态图标：柔和圆角底＋三道文字线，尺寸与线条都按 4px 刻度派生。
EMPTY_ICON_SIZE = SPACING["2xl"] + SPACING["xl"]
EMPTY_ICON_LINE = SPACING["xs"] // 2 + 1
EMPTY_TEXT_GAP = SPACING["sm"]

# 平滑滚动：滚轮把目标位置推远，每帧走剩余距离的 EASE 比例（缓出），剩余不足 SNAP_PX 像素就一步到位。
# 6 帧 × 16ms 内收敛；第一步在滚轮事件里同步走，所以滚轮后立刻就有反馈。
SCROLL_EASE = 0.5
SCROLL_FRAME_MS = 16
SCROLL_SNAP_PX = 1

# 换页冻结绘制：旧页留在屏幕上，新页布局稳定后一次画出；最长冻这么久，超时照常解冻。
PAGE_FREEZE_MAX_MS = 800

# 按钮悬停渐变：总时长 HOVER_FADE_MS 分 HOVER_FADE_STEPS 档（中间 STEPS-1 档是混色底图，按需生成并缓存）。
HOVER_FADE_MS = 100
HOVER_FADE_STEPS = 4

# 三虎插画色（R1851 后从 pet_ui_support／pet_ui 收拢）：只给桌宠绘制用，不进业务页面。
PET_PALETTE = {
    'fur': '#ff8a3d',
    'ear': '#ff9292',
    'muzzle': '#fff2d9',
    'ink': '#1a1c2a',
    'star': '#22d3ee',
    'blush': '#ff8d9b',
    'paw_idle_fill': '#e7edf5',
    'paw_idle_line': '#a9b6c7',
    'paw_hover_fill': '#f4f9ff',
    'paw_hover_line': '#6f8bab',
    'caption_ink': '#000000',
    'ice': '#eef5fc',
    'ink_soft': '#3c526d',
    'tongue': '#c98ba4',
    'mood_idle': '#7fb0dd',
    'mood_idle_line': '#101c2b',
    'mood_idle_deep': '#0a1521',
    'mood_busy': '#d9a63c',
    'mood_busy_line': '#2a1e05',
    'mood_busy_deep': '#1b1200',
    'mood_worry': '#d4645c',
    'mood_worry_line': '#2d0d0a',
    'mood_worry_deep': '#1c0603',
    'mood_paused': '#c2c8d2',
    'mood_paused_line': '#3a4048',
    'mood_paused_deep': '#20242a',
    'level_hint': '#6fb3e0',
    'level_hint_line': '#123a5e',
    'level_hint_deep': '#08182a',
    'level_semi': '#e0b13c',
    'level_semi_line': '#6b4a10',
    'level_semi_deep': '#241703',
    'level_auto': '#dd5f57',
    'level_auto_line': '#7c231e',
    'level_auto_deep': '#2a0806',
    'paused_muzzle': '#e3e6eb',
    'paused_ear': '#c7cbd2',
    'paused_blush': '#c0a8ac',
    'glint': '#cfe7ff',
    'blush_cool': '#8fb6d8',
}
