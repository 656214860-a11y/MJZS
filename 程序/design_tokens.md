# UI 设计 Token

本文件是「漫剧助手」全部 UI 视觉取值的唯一权威。所有 Tk 页面、主题、组件与评审均以此为准。

## 颜色

| Token | 值 | 用途 |
| --- | --- | --- |
| `color.background.primary` | `#F7F9F9` | 主背景 |
| `color.background.card` | `#FFFFFF` | 卡片、输入框与次按钮背景 |
| `color.surface.hover` | `#EFF3F4` | 次按钮/文字按钮悬停面 |
| `color.surface.pressed` | `#DFE6E9` | 次按钮/文字按钮按下 |
| `color.border.default` | `#DCE3E7` | 弱分隔线：卡片、容器与 Tooltip 描边（原 #EFF3F4 在底色上几乎不可见） |
| `color.row.completed` | `#EFF3F4` | 表格「已完成」行底色 |
| `color.border.input` | `#CFD9DE` | 输入框默认描边 |
| `color.border.input.hover` | `#A9BAC4` | 输入框悬停描边 |
| `color.text.primary` | `#0F1419` | 主文字（白底 18.5:1） |
| `color.text.secondary` | `#536471` | 次文字（白底 6.1:1） |
| `color.text.muted` | `#616D76` | 弱文字（白底 5.3:1、悬停面 4.75:1；禁用态另用 `color.disabled.text`） |
| `color.text.heading` | `#0F1419` | 标题文字（与正文同灰度，靠字重区分） |
| `color.primary` | `#2E3842` | 主按钮、强调（深石墨高级灰；与白 11.8:1、与页面底 11.2:1） |
| `color.primary.subtle` | `#E9EEF1` | 主色浅底（雾灰续写条/轻底） |
| `color.primary.hover` | `#212931` | 主色悬停（深石墨加深，白字 14.7:1） |
| `color.primary.pressed` | `#161C22` | 主色按下（炭黑加深，白字 17.2:1） |
| `color.focus` | `#4B5A68` | 键盘焦点环 / 输入框聚焦描边 |
| `color.accent` | `#64748B` | 装饰色（冷石板灰；聚焦环、侧边指示条等非文字用途，不作按钮底色或文字色） |
| `color.danger` | `#DC2626` | 危险操作与错误 |
| `color.danger.hover` | `#B91C1C` | 危险悬停 |
| `color.danger.pressed` | `#7F1D1D` | 危险按下 |
| `color.danger.text` | `#991B1B` | 错误文字 |
| `color.danger.subtle` | `#FEF2F2` | 错误提示底色 |
| `color.success` | `#15803D` | 成功状态（由 #16A34A 加深一档，白字 5.0:1） |
| `color.success.text` | `#15803D` | 成功文字 |
| `color.success.subtle` | `#DCFCE7` | 成功提示底色（统一状态栏 success 级消息，R2984 起） |
| `color.warning` | `#D97706` | 警告状态（只作状态与文字，不作按钮底色） |
| `color.warning.text` | `#B45309` | 警告文字（白底 5.0:1） |
| `color.secondary.bg` | `#E8EDF0` | 默认 TButton 族柔和浅灰底 |
| `color.secondary.hover` | `#DCE3E7` | 默认按钮悬停（浅灰加深） |
| `color.secondary.pressed` | `#CFD8DE` | 默认按钮按下（中浅灰加深） |
| `color.secondary.text` | `#1F2933` | 默认按钮深炭灰文字（对三态底色均 >10:1） |
| `color.disabled.bg` | `#F3F4F6` | 禁用背景 |
| `color.disabled.text` | `#9CA3AF` | 禁用文字 |
| `color.border.strong` | `#D1D5DB` | 分组框、容器边框 |
| `color.header.bg` | `#F7F9F9` | 表头背景 |
| `color.code.background` | `#F3F4F6` | 代码块底色 |
| `color.trough` | `#EFF3F4` | 进度条槽 |
| `color.selection.bg` | `#E5EBEF` | 表格/项目卡片选中雾灰背景 |
| `color.selection.text` | `#141B22` | 选中深炭文字 |
| `color.selection.border` | `#BDC8D0` | 选中冷灰描边 |
| `color.progress` | `#3D4B58` | 进度条 |
| `color.row.done.bg` | `#EFF3F4` | 已完成行柔和灰底色 |
| `color.on.accent` | `#FFFFFF` | 实心按钮（主／危险／成功／听写中）上的文字色；与表面色拆开，夜间仍是白字（REQ-UI-THEME-1） |
| `color.primary.text` | `#33414E` | 主色用作页面文字（进度提示、文字按钮）时的深石板灰；夜间提亮一档（见「明暗主题」） |

## 明暗主题（REQ-UI-THEME-1）

界面主题收敛为简约明暗两套：日间（`day`，上表即日间板）与夜间（`night`）。两套调色板的语义键集必须一致，由 `tests/test_ui_theme.py` 的对比度用例钉死；所有颜色仍只从 `ui_tokens.COLORS` 取值，页面不得内联 hex。

| 规则 | 约定 |
| --- | --- |
| 生效机制 | `ui_tokens.set_theme(name)` 原地替换 `COLORS` 并同步派生 token 与已绑定常量；`current_theme()` 读当前主题；非法名字返回 `None` 不动现状 |
| 取值解析 | `resolve_theme(saved)`：`day`／`night` 直用；`system`、缺失或认不出跟随系统；`system_theme()` 读注册表 `AppsUseLightTheme`（0=夜间），读不到回落日间 |
| 持久化 | 设置页「基础功能」的「界面主题」下拉（跟随系统／日间／夜间）经 `stage_execution_service.publish_desktop_preferences` 写 `desktop_settings.json` 的 `theme` 键，不直写文件 |
| 切换生效 | 保存后立即 `set_theme`＋`Desktop.refresh_ui_theme()` 重挂样式与选项库；`refresh_native_widgets()` 同步重染已建原生控件、画布图元、脚本正文标签与已登记菜单，日夜切换不要求重开页面 |
| 新 token | `on.accent`（实心按钮字色）、`primary.text`（主色作文字）两套都必须登记；实心按钮字色一律用 `on.accent`，不得再借 `background.card` 当字色 |

夜间板取值（`ui_tokens._NIGHT_COLORS`，与日间板同键集）：

| Token | 夜间值 |
| --- | --- |
| `color.background.primary` | `#10151C` |
| `color.background.card` | `#1B2330` |
| `color.surface.hover` | `#26303F` |
| `color.surface.pressed` | `#2E3A4B` |
| `color.border.default` | `#3A4657` |
| `color.row.completed` | `#26303F` |
| `color.border.input` | `#46536A` |
| `color.border.input.hover` | `#5B6B85` |
| `color.text.primary` | `#E8ECF2` |
| `color.text.secondary` | `#A7B3C2` |
| `color.text.muted` | `#8B98A9` |
| `color.text.heading` | `#F2F5F9` |
| `color.primary` | `#475569` |
| `color.primary.subtle` | `#242E3B` |
| `color.primary.hover` | `#3A4758` |
| `color.primary.pressed` | `#2E3948` |
| `color.focus` | `#94A3B8` |
| `color.accent` | `#94A3B8` |
| `color.danger` | `#DC2626` |
| `color.danger.hover` | `#B91C1C` |
| `color.danger.pressed` | `#7F1D1D` |
| `color.danger.text` | `#F87171` |
| `color.danger.subtle` | `#2A1418` |
| `color.success` | `#15803D` |
| `color.success.text` | `#4ADE80` |
| `color.success.subtle` | `#12301F` |
| `color.warning` | `#D97706` |
| `color.warning.text` | `#FBBF24` |
| `color.secondary.bg` | `#283240` |
| `color.secondary.hover` | `#323E4F` |
| `color.secondary.pressed` | `#3C4A5E` |
| `color.secondary.text` | `#E2E8F0` |
| `color.disabled.bg` | `#232B38` |
| `color.disabled.text` | `#6B7686` |
| `color.border.strong` | `#46536A` |
| `color.header.bg` | `#161C26` |
| `color.code.background` | `#1E2632` |
| `color.trough` | `#10151C` |
| `color.selection.bg` | `#2B3646` |
| `color.selection.text` | `#E2E8F0` |
| `color.selection.border` | `#4B5B70` |
| `color.progress` | `#94A3B8` |
| `color.row.done.bg` | `#222B38` |
| `color.on.accent` | `#FFFFFF` |
| `color.primary.text` | `#CBD5E1` |

对比度约束（两套都成立，由可跑测试守卫）：正文文字对底 ≥4.5:1、次要文字 ≥3:1、实心按钮字色对填充 ≥4.5:1。

## 间距

所有间距只能使用下列 4px 倍数 token；不允许魔法数字。

| Token | 值 |
| --- | --- |
| `space.xs` | 4px |
| `space.sm` | 8px |
| `space.md` | 12px |
| `space.lg` | 16px |
| `space.xl` | 24px |
| `space.2xl` | 32px |

## 圆角

| Token | 值 | 用途 |
| --- | --- | --- |
| `radius.sm` | 4px | 小控件（图标钮、滚动条滑块） |
| `radius.md` | 8px | 按钮、输入框 |
| `radius.lg` | 12px | 卡片 |

圆角本轮起被真正消费：按钮与卡片由 `ui_widgets` 用标准库生成的带 alpha PNG 图元绘制，输入框保持矩形（见「输入框」）。

## 字体

字体统一使用系统 `Microsoft YaHei UI`，单位是 Tk 的 pt（Windows 96 DPI 下 10pt 约 13px）；不随包分发字体。层级收敛为四档，页面只能取下表 token，不得手写字号。

| Token（`ui_tokens.FONTS`） | 字体 | 用途 |
| --- | --- | --- |
| `heading_1` | 微软雅黑 UI 16 bold | 页面标题 |
| `title` / `heading_2` | 微软雅黑 UI 14 bold | 区块标题、弹窗标题 |
| `body` / `caption` | 微软雅黑 UI 10 | 正文、表单、按钮、表格、说明；本文其它章节写的 `font.body`＝`body`，`font.assistive`＝`caption` |
| `body_bold` | 微软雅黑 UI 10 bold | 正文内强调 |
| `hint` | 微软雅黑 UI 9 | 辅助提示（最小可读字号，不再往下缩；已删除中文斜体） |
| `numeric` / `code` | Consolas 10 | 数字、代码 |
| `heading_3` / `heading_4` | 微软雅黑 UI 12 / 11 bold | 仅用于 Markdown 阅读区（技能说明、剧本内容）内部层级 |
| `pet_body` / `pet_hint` | 微软雅黑 UI 9 / 8 | 仅三虎气泡 |

`caption` 与 `body` 当前同为 10pt，是有意合并：说明文字靠颜色（`text.secondary`）而不是更小字号区分层级。

## 控件尺寸与密度（2026-10-21 密度放松）

主界面走“平静、专业、透气”的桌面密度，宠物层保留个性。

| Token | 值 | 规则 |
| --- | --- | --- |
| `CONTROL_HEIGHT` | 36px（`space.2xl + space.xs`） | 按钮、单行输入、下拉框、数值框的视觉高度；同一行的控件必须同高 |
| `CONTROL_PADDING_Y` | 8px（`space.sm`） | 单行输入／下拉框／数值框的上下内边距；按钮同样沿用 |
| `BUTTON_MIN_WIDTH` | 11 字符 | 所有按钮样式显式声明的最小宽度（原 clam 隐含值）；同组要按文字自适应的按钮传 `width=0` |
| `BUTTON_GAP` / `BUTTON_GAP_TIGHT` | 8px / 4px | 同行按钮间距；4px 仅限图标按钮与紧凑行 |
| `NAV_PADDING_X` / `NAV_SUB_PADDING_X` / `NAV_PADDING_Y` / `NAV_PADDING_Y_COMPACT` | 10 / 16 / 4 / 1px | 侧栏导航按钮内边距；R2897 图标轨后一级导航用 `SPACING['xs']`(4px)、二级「资产清单」用 `NAV_SUB_PADDING_X`；矮窗口只经 `ui_rounded.set_button_padding` 改，按下态同步 |
| `NAV_ROW_HEIGHT` / `NAV_ROW_HEIGHT_COMPACT` | 24 / 20px | 侧栏项目树行高；`fit_sidebar` 矮窗口切换，Compact／Nav／RailIcon 各变体（含 Selected）同步内边距 |
| `CONTROL_HIT_MIN` | 36px | 任何可点击元素的最小点击区；小于它的图标要外扩点击区（宠物齿轮、猫爪待迁移） |
| `BUTTON_RADIUS` | `radius.md`（8px） | 按钮圆角半径 |
| `CLOSE_BUTTON_STYLE` / `CLOSE_BUTTON_COMPACT_STYLE` / `CLOSE_BUTTON_COMPACT_ACTIVE_STYLE` | `Tokens.Close.TButton` / `Tokens.Close.Compact.TButton` / `Tokens.Close.Compact.Active.TButton` | 全应用统一关闭 × 按钮样式（S02/S03 编辑器、状态栏消息历史浮窗、三虎云朵用主样式；S01 模型目录条按未选/选中底色用紧凑变体）；`ui_hover_fade` 跳过 `Tokens.Close.*`，避免悬停第 0 帧白底白×闪烁 |
| `CLOSE_BUTTON_FONT` / `CLOSE_BUTTON_COMPACT_FONT` | `FONTS['heading_2']`（14 bold）/ `FONTS['heading_3']`（12 bold） | 关闭按钮加粗放大 `×` 字形（`CLOSE_BUTTON_MARK = '×'`）；圆角 `CLOSE_BUTTON_RADIUS = radius.sm`（4px），内边距 `CLOSE_BUTTON_PADDING = (space.xs, 0)`，请求尺寸落在 22–30px；常态取 `background_card`/`primary_subtle`＋`text_secondary`，悬停切 `danger`＋`on_accent`，按下切 `danger_pressed`＋`on_accent` |
| `STATUS_BAR_FONT` | `FONTS['body']`（微软雅黑 UI 10） | 底部状态栏全栏同一字号：左区各段、分隔符、右区消息 |
| `STATUS_BAR_SEGMENT_MAX_WIDTH` | 28 字符 | 状态栏左区一段的宽度上限：不超过就按文字本身的宽度显示，超过才截断并在悬停时给全文 |
| `STATUS_BAR_SEPARATOR` / `STATUS_BAR_SEPARATOR_GAP` | `·` / 8px（`space.sm`） | 状态栏左区相邻两段之间的分隔符，和它两侧各留的间距 |
| `STATUS_BAR_EDGE_PAD` | 8px（`space.sm`） | 状态栏左区开头、右区消息左右的留白 |
| 焦点环 | `focuscolor` = `color.focus` | 所有可操作控件必须有可见键盘焦点 |

**36px 计算式（100% DPI）**：ttk 控件没有 height 属性，高度 = 字体行高 + 2×上下内边距 + 主题边框/焦点占位。10pt 微软雅黑 UI 的 `linespace` 实测 19px。

- 按钮：圆角图元高 `CONTROL_HEIGHT`（36px），文字 19px + 2×`CONTROL_PADDING_Y`(8) 仍落在图元内；
- 单行输入／下拉框／数值框：`19 + 2×8 + 2×1px 边框 = 37px`。

两者都落在 36±2px 内；`tests/test_ui_style_engine.py` 用真 Tk 根窗口实测 `winfo_reqheight()`，非 100% 缩放按 `tk scaling` 折算。唯一定义处是 `ui_widgets.setup_styles()`；`ui_theme.apply()` 只装主题并调用它。

**圆角按钮规则（2026-10-21）**：按钮常态用圆角图元（`ui_rounded.py` 用标准库生成的带 alpha PNG，按 (颜色, 半径, 尺寸) 缓存）取代 raised 浮雕；样式 `background` 取 `CONTROL_CORNER_SURFACE`（按钮背后的页面底），填充色走 `fill` 选项，否则圆角会被填成方角；悬停加深一档、按下再深一档并让文字下移 1px。主按钮实心 `color.primary`，次按钮白底＋输入框级描边（`color.border.input`，在页面底上清晰可见），新增文字按钮无底、悬停浅底（`color.surface.hover`）。既有样式名全部保留，只改外观不改名。

主色收敛为深石墨高级灰一套（对齐应用目录图标与文件图标的冷中性墨色体系）：橙色／琥珀色不再作按钮或强调底色（旧 `emphasis`、`warning.hover`、`warning.pressed` 已删除），亮蓝与浅绿提示底色亦退场。需要“醒目”的按钮用更深一档的 `color.primary.pressed`。文字与底色的对比度不低于 4.5:1。

## 窗口尺寸

| Token | 值 | 规则 |
| --- | --- | --- |
| `DESKTOP_LAYOUT['default_width']`／`['default_height']` | 1280×800 | 主窗口首次尺寸 |
| `DESKTOP_LAYOUT['min_width']`／`['min_height']` | 1024×600 | 主窗口最小尺寸（2026-11-27：按 1366×768 与 1080p@150% 工作区折中，不用 1280×720） |
| `DESKTOP_LAYOUT['window_margin_x']`／`['window_margin_y']` | 24px／48px | 屏幕可用区小于默认值时保留的边缘留白 |
| `DIALOG_MIN_WIDTH`／`DIALOG_MIN_HEIGHT` | 240×160 | 弹窗最小尺寸；由两个 96px 按钮并排（约 236px）和标题＋两行说明＋动作区（约 160px）得出 |

`ui_theme.main_window_size()` 返回 `min(默认值, 可用区 − 边距)`，永不超过可用区；`desktop.Desktop.__init__` 与 `ui_theme.install_window_placement` 共用这组值。弹窗定位只允许缩到 240×160，不再降到 1×1。

## 下拉框（Combobox）

下拉框的视觉由 `ui_widgets.setup_styles(root)` 一次性应用；业务页面不得自行指定颜色、字体、边框或内边距。业务页统一使用 `SelectBox`：只读选项按 ASCII=1、CJK=2 估算最长宽度，封顶 28；空选项及可编辑框默认宽度 15。布局需要时可显式覆盖宽度。弹出列表默认最多 12 行，超出由原生滚动条承载。

| Token | 值 | 用途 |
| --- | --- | --- |
| `combobox.width` | 15 字符 | 空选项及可编辑框的默认宽度 |
| `COMBOBOX_MAX_WIDTH` | 28 字符 | 只读框自适应宽度上限 |
| `COMBOBOX_POPDOWN_HEIGHT` | 12 行 | 弹出列表默认最大行数 |
| `combobox.font` | `font.body` | 输入区和下拉列表文字 |
| `combobox.padding` | `space.sm` × `CONTROL_PADDING_Y`（6px） | `SelectBox` 统一控件样式的水平／垂直内边距 |
| `combobox.field.background` | `color.background.card` | 可编辑与只读字段背景 |
| `combobox.foreground` | `color.text.primary` | 正常文字 |
| `combobox.arrow.color` | `color.text.secondary` | 下拉箭头；主题不支持时安全回退系统箭头 |
| `combobox.list.selection` | `color.selection.bg` + `color.selection.text` | 弹出列表选中项背景／前景 |
| `combobox.focus` | `color.focus` | 字段获得焦点时的边框色 |

`SelectBox` 固定使用 `Tokens.Combobox.TCombobox`（`COMBOBOX_CONTROL_PADDING = (space.sm, CONTROL_PADDING_Y)`）；旧 `TCombobox` 基样式保留 `COMBOBOX_PADDING` 供默认继承，页面不得直接构造裸 `ttk.Combobox`。

## 输入框（LineInput／TextArea）

单行输入必须使用 `ui_widgets.LineInput`，多行输入必须使用 `ui_widgets.TextArea`。组件统一占位文字、只读态和错误边框；页面仅提供字段内容、尺寸和领域校验，不得重写视觉参数。全局 `TEntry` 与 `TSpinbox` 样式同样只在这里定义：10pt 字体、`(space.md, CONTROL_PADDING_Y)` 内边距、1px 边框，焦点边框为 `color.focus`；`TextArea` 是多行控件，不套用 32px 控件高度。

| Token | 值 | 用途 |
| --- | --- | --- |
| `input.font` | `font.body` | 单行与多行正文 |
| `input.foreground` | `color.text.primary` | 正常输入文字 |
| `input.placeholder.foreground` | `color.text.secondary` | 占位文字 |
| `input.background` | `color.background.card` | 输入区底色 |
| `input.border` | `color.border.input` | 默认 1px 边框 |
| `input.border.hover` | `color.border.input.hover` | 悬停边框 |
| `input.error.border` | `color.danger` | 校验失败边框 |
| `input.focus.border` | `color.focus` | 获得焦点时的描边（LineInput／SelectBox）；TextArea 用 `highlightcolor` 表达同一焦点色 |
| `input.text.selection` | `color.selection.bg` + `color.selection.text` | Tk Text/Listbox 与下拉弹出列表的选区背景／文字 |
| `input.text.cursor` | `color.text.primary` | Tk Text 插入光标，日夜两套都对输入底色可读 |
| `input.padding` | `space.lg` × `CONTROL_PADDING_Y`（8px） | 水平／垂直内边距；垂直值使单行控件落在 36±2px |

输入框保持矩形（ttk.Entry／TCombobox 的图元改造会破坏占位、只读、错误态或下拉行为，故不为圆角牺牲既有行为）。

## 文字层级

三类辅助文字只能由 `ui_widgets.HintLabel`、`DescriptionBlock`、`ProgressLabel` 构建。Tk 的 Label 没有独立行距属性，`*.linespace` 以组件统一的垂直内边距表达；页面不得自行覆写字体、颜色、折行或内边距。

| Token 组 | 用途 | 字体／颜色 | 最大内容与折行 |
| --- | --- | --- | --- |
| `text.hint` | 输入空态、图标旁短提示 | `font.assistive` / `color.text.secondary` | ≤20 字；240px 内左对齐折行；`space.xs` 行距/纵向留白 |
| `text.desc` | 功能说明、按钮下方或区块底部 | `font.body` / `color.text.secondary` | ≤60 字；560px 内左对齐自动折行；`space.sm` 行距/纵向留白 |
| `text.progress` | 状态栏、页面底部进度 | `font.body` / `color.primary` | 单行优先、≤40 字；480px 左对齐兜底折行；`space.xs` 行距/纵向留白 |

## 弹窗

弹窗仅由 `ui_widgets.BaseDialog`、`FormDialog`、`ConfirmDialog` 构建。标题栏、内容区与底部按钮区不得由业务页自行设定视觉参数；危险确认主按钮复用既有 `color.danger`。

| Token | 值 | 用途 |
| --- | --- | --- |
| `dialog.title.font` | `font.title` | 弹窗标题 |
| `dialog.content.padding` | `space.lg` | 标题、内容区的水平留白与内容区内边距 |
| `dialog.action.height` | `space.xl` | 底部按钮区最小高度 |
| `dialog.action.gap` | `space.sm` | 按钮之间的间距 |

## 通知

通知的严重级别复用既有 `color.danger`、`color.warning`、`color.success` 语义；`NotificationDispatcher` 负责将业务消息投递到既有状态栏，并只在调用方明确要求时复用系统模态提示。通知组件不新增另一套颜色或窗口 token。

## Tooltip

Tooltip 仅由 `ui_widgets.Tooltip` 建立；页面不得自行创建无边框 `Toplevel` 或复制鼠标进入／离开的延迟销毁逻辑。它用 `font.assistive`、`color.text.primary`、`color.background.card` 与 `color.border.default`，内容留白为 `space.sm` × `space.xs`，相对控件偏移为 `space.sm`。显示延迟统一为 400ms；鼠标悬停和键盘焦点进入均可触发，离开、失焦或控件销毁必须取消等待并销毁浮层。

## 表格（DataTable）

业务页通过 `ui_widgets.DataTable` 建立新表格；它统一列标题、滚动条、选择回调、按列排序和空态，页面只提供列定义、数据与领域单元格行为。

### 滚动条

标准 `ttk.Scrollbar` 的轨道、滑块和悬停色仅由 `ui_widgets.setup_styles()` 读取 `ui_tokens.py` 的 `SCROLLBAR_*` token 设置（本轮从 `ui_theme.apply()` 迁入）；业务页面不得为单个滚动条内联颜色、边框或另建 Style。横向和纵向使用同一视觉与 active 反馈：无箭头、厚度 `SCROLLBAR_WIDTH`（8px）、滑块常态取 `color.border.input`、悬停取 `color.border.input.hover`、轨道与背景同色；日夜两套语义一致。

| Token | 值 | 用途 |
| --- | --- | --- |
| `table.header.font` | `font.body` | 列标题 |
| `table.row.font` | `font.body` | 数据行 |
| `table.row.height` | `space.xl` | 默认行高 |
| `table.empty.padding` | `space.lg` | 空态留白 |

## 图标

| Token | 值 | 用途 |
| --- | --- | --- |
| `icon.nav.size` | 24px | `scripts/build_nav_icons.py` 的 `render_icons()` 生成的主导航 PNG 固定画布边长（含 `project_files.png`）；M3 `render_stage_file_icons()` 生成的 13 个 `<stage>_files.png` 复合图标按内容裁边，不适用此尺寸门禁。运行时只读 PNG。 |

图标取用边界（MDL2 字形 vs Fluent PNG）见 `ui_components.md`「图标」节。

## 框体（Box）

聊天框、内容框、列表框的统一外框组件 `Box`（创建入口 `ui_theme.box_frame()`，`Box.TFrame` 样式升格）：

| 属性 | Token / 规则 |
| --- | --- |
| 边框色 | `color.border.strong` |
| 边框 | 直角、1px（`relief='solid'`、`borderwidth=1`） |
| 背景 | `color.background.primary` |
| 内边距 | `space.sm`（内容区与 1px 边框之间的呼吸距） |

`Box` 与 `Card` 的分工见 `ui_components.md`「框体」节。

## 强制规则

1. 所有 `padx` / `pady` 必须取自 `space.*`；禁止魔法数字。
2. 所有颜色必须取自 `color.*`；禁止在页面或组件中内联 hex。
3. 所有圆角必须取自 `radius.*`。
4. 同一视觉层级的控件必须使用相同字体 token 与字号。
5. 新增、修改 UI 时必须先选定 token；评审必须检查本文件与 `ui_components.md` 的遵循情况。

## 三虎气泡（R1449）

- `font.pet_body`：Microsoft YaHei UI 9；正文、编号与回复框。
- `font.pet_hint`：Microsoft YaHei UI 8；底部灰色提示。
- `PET_CLOUD_AUTO_CLOSE_MS`：10000ms；悬停或回复框有焦点时暂停，交互结束后完整重计。
