# UI 组件契约

本文件定义项目可复用 UI 组件的唯一写法。组件的颜色、间距、圆角和字体均引用 `design_tokens.md`；页面不得自行变体。

## 主按钮

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.primary`（圆角图元，标准库生成的带 alpha PNG） |
| 文字 | 白色 |
| 边框 | 无可见边框：圆角图元取代 raised 浮雕；仅键盘焦点时为 `color.focus` |
| 圆角 | `radius.md`（本轮起真正消费） |
| 字体 | `font.body`（10pt），不再用 11pt bold |
| 尺寸 | 视觉高度 `CONTROL_HEIGHT`（36px）；水平内边距 `space.md`、垂直 `CONTROL_PADDING_Y`（8px）；Tk 实测 37px（36±2） |
| 悬停 | 背景 `color.primary.hover`（加深一档），文字白色 |
| 按下 | 背景 `color.primary.pressed`（再深一档），文字下移 1px |
| 禁用 | 背景 `color.disabled.bg`，文字 `color.disabled.text` |
| 焦点 | `focuscolor` = `color.focus` |

用于页面的首要、提交、确认动作；同一操作组最多一个主按钮。需要比主按钮更醒目的花钱步骤（如“MCP 优化”）用 `Highlight.TButton`（更深一档的 `color.primary.pressed`），不使用橙色。

**唯一样式来源**：`ui_widgets.setup_styles()` 是按钮、输入框、下拉框、数值框、卡片与滚动条样式的唯一定义处（按钮在 `_install_button_styles()`，输入在 `_install_input_styles()`，滚动条在 `_install_scrollbar_styles()`）；`ui_theme.apply()` 只安装主题、选项库与窗口策略，末尾调用 `setup_styles()`。页面不得再用 `ttk.Style` 配置同名样式，也不得另建局部 Style。

**36px 怎么来**：Tk 的 ttk 控件没有 height 属性。按钮高度 = 字体行高 + 2×`CONTROL_PADDING_Y`（圆角图元不额外撑内边距，`padding=(0,0,0,0)`），`19px + 2×8px` 加焦点占位≈37px；输入类 `19 + 2×8 + 2×1px 边框 = 37px`。两者都落在 36±2px；`tests/test_ui_style_engine.py` 用真 Tk 根窗口实测 `winfo_reqheight()`，非 100% 缩放按 `tk scaling` 折算。

**圆角规则（2026-10-21）**：按钮常态用圆角图元取代 raised 浮雕；悬停加深一档、按下再深一档并让文字下移 1px（上加下减，按钮总高不变）。**样式的 `background` 必须是控件背后的表面色（`CONTROL_CORNER_SURFACE`），按钮填充色放在自定义选项 `fill`（含 active／pressed／disabled 映射）里**：ttk 把圆角透明处露出的是样式 `background`，若它等于填充色，四个角会被填成实心方角。圆角底图由 `ui_rounded.py` 用标准库生成（无 PIL），图对象缓存在 Tk 根窗口上永久保留。主按钮实心、次按钮白底＋弱描边、文字按钮无底悬停浅底；既有样式名全部保留，只改外观不改名。

**唯一例外**：侧栏可用高度低于 `DESKTOP_LAYOUT['compact_below']` 时，`Desktop.fit_sidebar()` 会只缩小 `Compact.TButton`／导航按钮／`ProjectAction.TButton` 的字号与纵向内边距，以便 14 个阶段仍可见；它不定义颜色、背景或焦点色，窗口回到常规高度后仍以本入口的 36px 规则为准。

## 次按钮

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.background.card`（圆角图元） |
| 边框 | 极淡描边：1px `color.border.default`（弱分隔线色）；仅键盘焦点时为 `color.focus` |
| 文字 | `color.text.primary` |
| 圆角 | `radius.md` |
| 字体与尺寸 | 同主按钮：`font.body`、高度 `CONTROL_HEIGHT`、水平内边距 `space.md` |
| 悬停 | 背景 `color.surface.hover`，文字 `color.text.primary` |
| 焦点 | `color.focus` 焦点环 |

用于次要、返回、刷新等不应抢占主动作视觉层级的操作。

## 卡片

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.background.card`（圆角图元） |
| 边框 | 极淡描边：1px `color.border.default` |
| 圆角 | `radius.lg`（本轮起真正消费） |
| 内边距 | `space.xl` |

卡片承载一个完整的信息或操作单元；同一卡片内的标题、正文与辅助文字分别使用对应字体 token。

## 输入框

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.background.card` |
| 边框 | 1px `color.border.input`，悬停 `color.border.input.hover` |
| 圆角 | 保持矩形（ttk.Entry／TCombobox 图元改造会破坏占位／只读／错误态／下拉行为） |
| 内边距 | `padx=space.lg`，`pady=CONTROL_PADDING_Y`（8px） |
| 尺寸 | 视觉高度 36px（`19px 行高 + 2×8px + 2×1px 边框 = 37px`，36±2） |
| 焦点 | 描边 `color.focus`（＝`color.primary`）；TextArea 用 `highlightcolor` 表达同一主色 |
| 正文 | `font.body` + `color.text.primary` |
| 提示/辅助 | `font.assistive` + `color.text.secondary` |

| 组件 | 使用时机 | 规则 |
| --- | --- | --- |
| `LineInput` | 单行名称、短文本或编码字段 | 使用 `placeholder`、`set_error()`、`set_readonly()` 表达状态；业务页不得直接构造 `ttk.Entry`。 |
| `TextArea` | 梗概、备注、说明等多行字段 | 使用同一套占位、只读和错误态；业务页不得手拼 `tk.Text` 的字体、边框、颜色和内边距。 |
| `SelectBox` | 选项选择 | 统一套用 `Tokens.Combobox.TCombobox`，与 `TEntry`／`TSpinbox` 同高；见“下拉框”。 |
| `TSpinbox` | 数值（小时、分钟、阈值） | 直接使用全局 `TSpinbox` 样式，不另写字体、内边距或颜色。 |

既有历史输入框按独立轮次迁移；首迁页面是“填写创作信息”表单，字段保存接口仍按 `Text.get('1.0', 'end-1c')` 读取，组件不得改变其结果。

## 通知

`ui_widgets.NotificationDispatcher` 是错误、警告、成功与一般提示的唯一分发入口。调用方只提供业务文案、级别和是否需要模态提示；分发器先更新既有状态栏，模态提示仍复用 Tk 的 `messagebox`，不另建第二套窗口。R2989 起支持注入统一状态栏总线（`bus=`）：有总线时通知走四级消息生命周期（error/warning 常驻、info/success 自动消失、进历史），旧 StringVar 由总线镜像回写；无总线宿主（独立设置窗）沿用原状态栏路径。新建页面不得直接组合 `status.set()` 与 `messagebox.show*()` 表达同一结果；历史页面按独立轮次迁移。

**错误策略（R1689 裁决，UI 批次 2 落地）**：可恢复的错误（网络、模型、校验）默认非模态——`NotificationDispatcher.error()` 默认 `modal=False`，只把完整文案落到状态栏，不弹系统框、不锁界面；需要“查看详情／重试”的页面自行在动作附近提供。只有删除、覆盖等破坏性确认保留模态，但它们走 `ConfirmDialog`／`ask_confirmation`，不在本函数内。仅当后续代码确实必须等用户关掉提示才能继续时，调用方才显式传 `modal=True` 并写明理由。状态栏颜色按级别区分（就绪中性、成功绿、警告、错误红），不再一律绿色。

## 统一状态栏（文字提示模块，R2984 起；UX-C4 起左区按内容排布）

应用只保留一条全局底部状态栏 `ui/ui_status_bar.py:StatusBar`，散落的文字提示统一为一个模块：

| 区段 | 内容 | 规则 |
| --- | --- | --- |
| 左区（常驻） | 页标题「NN 名称」、项目路径、Token/¥/余额（点击开用量详情）、模型用量摘要 | 每段一个 `SegmentLabel`（`EllipsisLabel` 的子类）：宽度按文字定，超过 `STATUS_BAR_SEGMENT_MAX_WIDTH`（28 字符）才截断、悬停 Tooltip 全文；调用方给了 `width` 的段维持那个宽度；文字为空的段不占位，再有文字时回到登记时的位置；点击展开详情；无数据时段隐藏，不显示假 0 |
| 右区（消息） | 四级消息 info/success/warning/error | error/warning 常驻直到被处理或下一条替换；info/success 约 8 秒自动消失；错误仍写日志；没有消息时显示中性提示「就绪」，字色和左区各段同一档灰 |
| 历史 | 点击右区展开最近 N 条 | 含时间、级别、全文；不另开窗口 |

- 左区排布（UX-C4）：看得见的段两两之间放一个分隔符 `STATUS_BAR_SEPARATOR`，分隔符两侧各留 `STATUS_BAR_SEPARATOR_GAP`；第一段前、最后一段后不放，中间的段隐藏时也不会出现两个连着的分隔符。段、分隔符、右区消息同用 `STATUS_BAR_FONT`，段和分隔符同用样式 `Muted.TLabel`（`color.text.secondary`）。左区开头、右区消息左右的留白都是 `STATUS_BAR_EDGE_PAD`。
- 别的模块直接 `pack` 进 `StatusBar.left_zone` 的控件（现在只有用量指示 `ui/ui_usage_indicator.py`）算一段：位置按它摆进来时已登记的段排，两侧的留白由状态栏改成 0、分隔符由状态栏补；它没有内容（宽度不到 2 像素）时不配分隔符。这类控件自己不要在两端留白，字体用 `STATUS_BAR_FONT`；新增左区内容优先用 `set_segment`。
- 消息唯一入口 `ui/ui_status_bus.py:StatusBus.publish(Message(level, text, ttl, source))`；业务模块只发消息，不得直接写状态栏（`status.set`）或组合 `messagebox`；`NotificationDispatcher` 保留为分级渲染的既有入口，内部转交 StatusBus。
- 视觉取值一律引用 `design_tokens.md`：就绪 `color.text.secondary`（UX-C4 起，和左区同一档）、成功 `color.success`／`color.success.subtle`、警告与错误沿用 `color.danger.text`／`color.danger.subtle` 及既有 `status_kind` 样式；圆角、间距、字体只取 token。
- 顶部标题行自 R3016 起已删除：原页头状态／模型名信息等价迁移（视频页模型/状态进左区段 `video_model`/`video`、剧本页流程说明进 `script_note`、分镜页「当前 JSON」进 `storyboard`），功能不丢；页标题进左区 `page` 段，侧栏图标轨上移填空。

## 右键菜单

`ui_widgets.ContextMenu` 是右键菜单的构建、定位和 grab 释放入口。页面只声明菜单项与领域回调；历史菜单按独立轮次迁移。

## 文件／目录选择

`ui_dialogs.FileDialog` 是文件与目录选择的唯一入口。页面只传入标题、初始目录和类型；取消统一返回空元组，窗口打开失败通过既有 `NotificationDispatcher` 显示可见错误。历史直接 `filedialog` 调用按独立轮次迁移。

## 快捷键

`ui_shortcuts.ShortcutRegistry` 是页面快捷键的登记入口。页面以稳定的作用域、语义名称和 Tk 序列注册快捷键；同一作用域的规范化重复序列会立即拒绝，以便集中审计冲突与后续帮助提示。历史直接 `bind()` 按独立轮次迁移。

## Tooltip

`ui_widgets.Tooltip` 是截断名称或图标含义等短说明的唯一浮层入口。页面传入目标控件和完整说明即可；组件统一 300ms 出现延迟、150ms reshow 窗口、鼠标悬停与键盘焦点触发，以及离开、失焦、销毁时的取消与清理（R2997 起为完整状态机：排程先取消旧计时器、卡片模式 300ms closeDelay 移出隐藏并复核指针、点击控件执行原动作并抑制重弹直到指针离开再进入；`mode='card'`＋`pin_on_click=True` 可点击钉住，点空白/Escape/再点解除，钉住期间悬停不触发）。Tooltip 不取得焦点或 grab，不能承载操作按钮、表单或长篇说明；后两类分别使用既有弹窗或 `DescriptionBlock`。

`ui_icons.IconLoader` 是页面图标位图的唯一构建入口。页面按语义名称请求图标，图标尺寸由入口参数统一，并按 Tk 宿主缓存；不得在业务页直接建立 `PhotoImage`。图标不能表达完整文字说明时，配合 `Tooltip`，不以图标替代可访问标签。

标准 `ttk.Scrollbar` 的唯一视觉入口是 `ui_widgets.setup_styles()`（本轮从 `ui_theme.apply()` 迁入）：页面只声明方向和 `command`，不得给单个滚动条创建局部 Style 或内联视觉参数。表格优先由 `DataTable` 承载其横、纵滚动条。

## 文案与复制

`prompt_window.copy_text()` 是应用文本写入系统剪贴板的唯一入口：它用 `clipboard_lock` 串行化跨进程写入，失败返回可展示的原因；页面必须据此给出成功或失败状态，不能静默吞掉。`copy_preview()` 仅用于状态栏回执，会掩盖疑似凭据；复制到剪贴板的原文不被改写。固定动作术语使用“已复制…”与“复制失败：…”，避免页面自行创造不可检索的反馈文案。

## 忙碌／加载态

`ui_widgets.BusyState` 是主后台任务的加载态入口：调用方开始时传入状态文案和需要暂时禁用的控件，收尾时必须用同一对象恢复。组件只管理状态栏、进度条和控件状态，不拥有线程、任务队列或取消语义；自动任务和专用中断链保留既有编排入口。

## 下拉框

业务页必须通过 `SelectBox` 创建下拉框（继承 `ttk.Combobox`）。默认只读，选项自适应宽度封顶 28、弹出列表默认 12 行；可编辑框显式传 `state="normal"`。动态选项更新用 `set_values(values)`，需要保持显式布局宽度时传 `refit=False`；保留 textvariable/current/get 语义。`SelectBox` 固定套用 `Tokens.Combobox.TCombobox`，控件高度与 `TEntry`／`TSpinbox` 同档（36±2px）；`TCombobox` 基样式只作默认继承，不是页面入口。所有下拉框由 `ui_widgets.setup_styles(root)` 作为唯一样式入口。字段、只读态、弹出列表、字体、边框与内边距使用 `design_tokens.md` 的 `combobox.*` token；页面只负责选项、数据绑定和必要的内容宽度，不得复制颜色或字体配置。

## 文字组件

| 组件 | 使用时机 | 规则 |
| --- | --- | --- |
| `HintLabel` | 输入空态、图标旁短提示 | ≤20 字，次级灰、常规辅助字号。 |
| `DescriptionBlock` | 功能说明、按钮下方、区块底部 | ≤60 字，自动折行并保留较宽行距。 |
| `ProgressLabel` | 状态栏、页面底部进度 | 单行优先、≤40 字，使用主色强调。 |

三者的唯一构建入口为 `ui_widgets.py`，并只消费 `ui_tokens.py` 的 `TEXT_HINT`、`TEXT_DESC`、`TEXT_PROGRESS`。页面不得直接为 `ttk.Label` 设置 `foreground` 或 `font` 来替代这些语义组件。

## 弹窗

| 组件 | 使用时机 | 规则 |
| --- | --- | --- |
| `BaseDialog` | 任何新建的应用内弹窗 | 统一标题栏、内容区、底部动作区、`transient`、`grab_set`、Esc 关闭、首个可交互控件聚焦与销毁时释放 grab。 |
| `FormDialog` | 用户填写或编辑字段 | 继承 `BaseDialog`；表单字段放入 `content`，提交／取消必须用 `add_form_actions()`。 |
| `ConfirmDialog` | 询问、删除或不可逆确认 | 继承 `BaseDialog`；调用方经 `result`／`on_result` 接收确认态，危险主操作使用 `color.danger`。 |

业务页禁止新建裸 `tk.Toplevel(...)` 作对话框；已有历史弹窗按独立轮次迁移，不在一次组件改造中批量替换。

普通弹窗经 `ui_theme.install_window_placement` 首次定位时，宽高不超过主窗口，但**不小于内容的请求尺寸**：业务页写死的尺寸（如高 DPI 下的 `600x400`）装不下内容时撑到内容大小，主窗口偏小时也不压扁，只有系统工作区放不下时才让步。定位后的尺寸恰好等于自然尺寸（内容或调用方声明的最小尺寸）时只摆位置、不写死宽高，之后才加载的内容（如联网读回的设备列表）还能把窗口撑大；这类弹窗保留调用方声明的最小尺寸。写死尺寸的弹窗随后允许用户缩放，不以主窗口大小作为永久上限，也不沿用业务页面的固定大小或最小尺寸。新弹窗优先只给最小宽度、不写死高度。仍遵守系统桌面尺寸限制；无边框提示层、贴片不属于可缩放对话框。

弹窗最小尺寸由 `DIALOG_MIN_WIDTH`（240px）×`DIALOG_MIN_HEIGHT`（160px）兜底：至少并排放得下两个 96px 按钮＋12px 间距＋两侧 16px 留白（约 236→240），高度至少容下标题、两行说明和底部动作区。定位时只允许缩到这两个下限，不再降到 1×1。

## 窗口尺寸

主窗口首次尺寸由 `DESKTOP_LAYOUT['default_width']`×`DESKTOP_LAYOUT['default_height']` 决定，默认 1280×800；最小尺寸 `min_width`×`min_height` 为 800×600。屏幕可用区更小时，`ui_theme.main_window_size()` 按 `window_margin_x`（24px）／`window_margin_y`（48px）收缩，返回值永不超过可用区；用户之后仍可自由缩放。`desktop.Desktop.__init__` 与 `ui_theme.install_window_placement` 共用这组 token，不各写一套数字。

## 表格

新建表格必须使用 `ui_widgets.DataTable`，由它统一滚动条、空态、列标题、选择回调与通用文字排序；页面仅传入 `(字段名, 标题, 宽度)` 列定义，并保留领域专用的复选、单元格点击及内容自适应逻辑。历史 `ttk.Treeview` 按独立轮次迁移，禁止在业务页复制滚动条或空态实现。

需要空列表仍展示列头时传入 `empty_text=''`，由组件禁用覆盖标签；默认空态文案和其他页面行为不变。剧本准备的三个分类标题始终保留，文件行仍按内容压缩高度。

## 浮层与文字测宽

浮层有五种机制（`ui_popup.Flyout` 无边框 Toplevel、`desktop_shared_menus.AnchoredPanel`／`CandidatePopup` 的 `place` 浮层、`ui_tooltip.Tooltip`、`ui_widgets.ContextMenu` 的 `tk.Menu`），因机制不同不合并为同一基类；统一的是三件事：**文字测宽**、**定位钳位**（`ui_popup.monitor_bounds`，按锚点所在显示器取边界）与**卡片样式 token**（描边 `color.border.default`、圆角 `radius.md`、留白 `space.*`）。

- **入口**：U1 的三处试点及后续新测宽走 `ui_popup` 的共享函数——输入 `FONTS`／token 字体与文本集合，返回像素宽度，含上限钳位参数；用真实字体 `measure`，不做全角 2／ASCII 1 近似。既有 `responsive_ui`、`ui_widgets` 等直接测宽按门禁实测冻结，谁改谁迁；试点不代表全仓唯一实现。定位钳位只走 `ui_popup.monitor_bounds`。
- **禁止**：新代码不得直接调用 `font.measure`／`tkfont.Font.measure`，不得手写字符宽度近似（全角×2＋ASCII×1），不得为撑开宽度写魔法数字（如 `+14`）。
- **门禁**：`test_text_measure_boundary.py`（U1）。

## 图标（MDL2 与 Fluent PNG 的边界）

- **入口**：输入框图标行（✦、🎤 及其下拉面板行）取 `ui_tokens.ICON_FONT` 的 MDL2 字形（`ICON_*` 常量）；输入框以外的新桌面图标取 Fluent Filled PNG，一律经 `IconLoader.nav_icon`。主导航 PNG 固定 24×24 画布（`icon.nav.size`）；M3 的 13 个 `<stage>_files.png` 复合图标自动裁边，豁免主导航尺寸门禁（见 `design_tokens.md`）。
- **禁止**：新代码不得用 emoji 当图标；输入框图标行之外不得新增 MDL2 `ICON_*` 字形引用；不得绕过 `IconLoader.nav_icon` 直接读 PNG 或自配字形。MDL2 存量、阶段文件缺 PNG 时的 14 个 emoji 回退、回收站／清空／素材库三处旧符号及视频封面空态均按门禁的 AST 口径冻结，不改 REQ-S01-93 的缺图行为。
- **门禁**：`test_icon_source_boundary.py`（U3）、`test_nav_icon_size_boundary.py`（U2）。

## 框体（Card 与 Box 的分工）

- **Card**（`ui_widgets.Card`，圆角 `radius.lg`、描边 `color.border.default`）：表单类卡片容器，21 页在用，外观不动。
- **Box**（`ui_theme.box_frame()` 创建入口：直角、1px `color.border.strong`，样式名、边框色、内边距取 token）：聊天框、内容框、列表框的正式外框组件。
- **禁止**：新代码不得直接写 `style='Box.TFrame'`，不得自拼 1px 边框替代 `Box`。
- **门禁**：`test_box_boundary.py`（U5）。

## 发送键

圆形外框，中间 ↑；运行中换 ■。边框色 `color.border.input.hover`、无填充；悬停边框与图标变 `color.primary`；不可点用 `color.disabled.text`；尺寸与 ✦＋🎤 同档（`ICON_FONT`）。样式与圆形底图放 `ui/ui_composer_style.py`；运行中↔空闲的状态切换唯一入口保持 `desktop_script_pages.update_script_interrupt_button()`（REQ-S01-62／DES-S01-62）。不再使用 `assets/nav/send.png`／`stop.png`。

- **门禁**：行为由 `test_script_composer`／`test_shared_input_ui` 锚定（U4），无独立边界门禁。

## 字体

- **入口**：新代码只取 `ui_tokens.FONTS[...]`。
- **禁止**：不得写内联字体元组（`("微软雅黑 UI", 10)` 这类）。
- **门禁**：`test_font_boundary.py`（U6），存量按文件冻结。

## 原生控件

- **入口**：浮层与卡片内的新代码优先用 `ui_widgets` 语义组件（`PrimaryButton`／`SecondaryButton`／`Card`／`SelectBox` 等）与已登记 ttk 样式。
- **禁止**：浮层与卡片内新代码不得新增自配颜色的 `tk.Label`／`tk.Frame`；存量（集中在 `desktop_shared_menus.py`、`ui/stage_model_picker.py`）按门禁文件冻结。
- **门禁**：`test_native_control_boundary.py`（U6）。

## 表单控件

- **入口**：`Checkbutton`／`Radiobutton`／`Scale`／`Spinbox`／`Notebook` 新代码只用 `ui_theme` 已登记的样式名（`TCheckbutton`、`TNotebook.Tab` 等），不得内联配置外观。
- **禁止**：不得为表单控件自配颜色、字体、内边距或新建局部 Style。
- **门禁**：`test_form_control_boundary.py`（U6），存量按门禁文件冻结。

## 消息卡片与 HITL（文件卡片任务，R3102–R3138）

文件卡片任务新增的交互组件，已并入本契约的同一套 token 与组件规则：

| 组件 | 入口 | 说明 |
| --- | --- | --- |
| 消息 part 分派渲染 | `ui_part_renderers.render_parts(box, name, parts, host)` | REASONING／ARTIFACT／TOOL_CALL／TOOL_RESULT／SOURCE／FILE／DATA 逐类渲染进 Text 气泡；只消费 `ui_tokens`，动作经 `host` 回调注入 |
| HITL 审批卡／选择卡 | `ui_hitl` 的审批门三按钮与选择卡 | 按钮走 `PrimaryButton`／`SecondaryButton`；决策经 `on_decision` 回调 |
| 参数微调面板 | `ui_param_panel` | 温度／步数滑条走 `ttk.Scale`、画面比例走 `SelectBox` |
| 图片／缩略图卡与 Lightbox | `ui_media`（`open_lightbox` 等） | 缩略图卡、Lightbox、多候选对比、收藏 |
| 引用溯源 | `ui_citation.insert_citations(box, name, text, …)` | 正文 `[n]` 着色并绑定点击定位 |
| 树表行预览卡 | `desktop_file_card.TreeRowCard`（继承 `TreeRowTooltip`） | 悬停读完整文件名 |

这些组件的存量违规项按对应门禁登记冻结：表单控件门禁冻结的是 5 处 `tk.Listbox` 原生控件（`ui/asset_reference_import.py`、`ui/desktop_writing_snapshots.py`、`ui/script_outline.py`、`ui/skill_panel.py`、`ui/skill_panel_import.py`）；`ui_hitl` 的 `ttk.Radiobutton` 与 `ui_param_panel` 的 `ttk.Scale` 无外观选项、样式经主题继承，属合规使用、不在冻结清单。其余 token 取用与语义组件复用已符合标准。

## 复用规则

每个组件只能有以上一种写法。新增页面必须复用既有组件实现或先扩展本契约；不得在页面内复制、修改样式参数形成第二种写法。

**明暗主题（REQ-UI-THEME-1）**：界面只有日间／夜间两套调色板（`ui_tokens.THEMES`），语义 token 键集一致；页面仍只取 `COLORS`，不得感知主题名。实心按钮（主／危险／成功／Highlight／听写中）的文字色一律用 `color.on.accent`，主色用作页面文字用 `color.primary.text`，不得再借 `background.card` 当字色。圆角底图图元名带主题后缀，`setup_styles` 按「ttk 主题名｜明暗」重装；切换后已建成页面保留旧色，重开页面完全生效。

`Toplevel` 弹窗与普通页面遵循完全相同的 token 和组件规则：标题、内容区、输入框和操作按钮均不得退回通用 ttk 样式。主按钮悬停加深一档（`color.primary.hover`）保持白字；次按钮悬停为 `color.surface.hover` 底配主文字，二者文字都保持可读。

## 微交互与空态（`ui_motion.py`）

| 组件 | 入口 | 行为 | 令牌 |
| --- | --- | --- | --- |
| 行悬停 | `bind_row_hover(tree)`；`DataTable` 与侧栏项目树自动安装 | 鼠标划过的行背景在 `ROW_HOVER_STEPS` 帧内由底色淡入到 `surface_hover`；选中行不加；只增减 `row_hover` 标签，不动行上其他标签 | `ROW_HOVER_*` |
| 加载转圈 | `Spinner(master, host=控件)`，挂到 `BusyState(spinner=…)` | 忙碌时叠在 host 右端转一段主色圆弧，结束即撤并停定时器；主窗口挂在状态栏上 | `SPINNER_*` |
| 空态 | `EmptyState(master, 文案, anchor_widget=列表)`；`DataTable.empty_label` 同样带图标 | 柔和圆角图标（`ui_rounded.empty_icon_photo`，缓存在根窗口）在文字上方，居中盖在列表上 | `EMPTY_*` |

侧栏自 R2897 起为图标轨，R2933 收紧为纯图标，R2946 再迭代一轮：轨宽 96px，导航图标放大到 24px（`RENDER_PX` 48 超采样），阶段名「NN 名称」搬进侧栏滚动区顶端（`EllipsisLabel`，10pt 加粗，最长页名不截断，Tooltip 留全文）。页头 R2950 收成单行：Token 用量居左、状态／模型同行居右，与侧栏「NN 名称」同一水平带（`body_padding` 顶距收到 xs），行高只取用量块／右侧信息／阶段配置钮的最大请求高。项目区是分组图标＋新建/打开图标，常驻下拉框已删：点「在制作／已完成」分组图标＝切组并弹出该组项目的 `Flyout` 选择层（`_post_project_picker`，● 标当前项、右键项目菜单、「项目管理…」入口都在层里），再点同组图标收起。「05 资产管理」的二级入口「资产清单」默认不显示：点资产图标弹同一 `Flyout` 基座的单选层，选中进清单页、图标临时换 `asset_list.png`，再点图标回资产管理主页（`_assets_nav_toggle`）。未授权页把导航图标换成 `lock.png`（`refresh_nav_locks`）。侧栏顶部浮层（应用名）与页头标语已删；当前项目名只留窗口标题「当前项目：…」。

侧栏底部是固定 `sidebar_dock`（先于滚动区 pack，永不参与滚动）：设置入口第 R2946 期上移为图标轨末尾的 `settings_rail_button`（Fluent `settings.png`，`RailIcon.TButton`，点开既有设置 hub），底栏只剩 `pet_dock` 三虎簇——簇整体收成正方形（`_cluster_layout`：边长取内容宽／高较大者，`DOCK_ROOM` 初值即边长），左列猫头像（44px）＋等级小字紧贴其下（宽 `DOCK_CAPTION_ROOM`，一行／两行换行）、右列猫爪竖排（14px）贴右沿（`DOCK_PAW_RIGHT`）并对「头像＋小字」整组垂直居中，命中区右沿钳在 dock 内；`pet.patch_room` 随实测簇高同步底栏高度（`align_header`）。弹出选择层统一走 `ui_popup.Flyout`（无边框 Toplevel＋1px 描边壳），点外部／Esc／选中即关，监听挂主窗 `bind`/`unbind(funcid)` 精确摘除；定位钳位按锚点所在显示器取 `monitor_bounds`（R2950：主窗在副屏时不再被主屏宽度拽回）。

一级／二级导航胶囊的悬停（`surface_hover`）与选中（`surface_pressed` 浅灰胶囊、深色内容）由 `Nav.TButton` / `Selected.Nav.TButton` / `Sub.Nav.TButton` 的圆角底图提供；纯图标小按钮用 `RailIcon.TButton` / `Selected.RailIcon.TButton`；
页面边距、导航间距、状态栏间距取自 `DESKTOP_LAYOUT` 的 `body_padding`／`nav_gap`／`section_gap`／`status_gap`；底栏几何取自 `pet_ui_support` 的 `DOCK_*` 常量组。

## 动效与拖窗口（性能/资源轮）

| 能力 | 入口 | 行为 | 令牌 |
| --- | --- | --- | --- |
| 平滑滚动 | `ui_scroll.eased_scroll(canvas, steps)`；主页面、侧栏、`ScrollForm` 的滚轮都走它 | 滚轮推「目标位置」，每帧走剩余距离的一半（缓出）；第一步在事件里同步走完；连续滚轮累加；翻页键／拖滚动条等别处移动画布时放弃剩余动画；不可滚或设了 `yscrollincrement` 时退回原生滚动；位移距离与原生 `units` 一致 | `SCROLL_*` |
| 按钮悬停渐变 | `ui_hover_fade.install_hover_fade(root)`（`setup_styles` 自动安装）；对所有登记过圆角规格的 `ttk.Button` 样式生效 | 进出时临时切到派生样式 `Fade<k>.<原样式>`（`ui_rounded.button_specs` 登记的规格生成混色底图，按需生成并缓存），100ms 分 4 档，走完还原原样式；期间别处改了样式、按钮被禁用或销毁则立即停，不覆盖别人写的样式 | `HOVER_FADE_*` |
| 拖窗口只画外层框架 | `desktop_layout_resize.ResizeCoalescer(freeze=, thaw=)`；`LayoutMixin._freeze_content/_thaw_content` | 确认光标捏着外框时收起页面内容与侧栏内容（画布窗口项设 `hidden`），松手后先放回再补做整页重排；探测不到（降级路径）只合并、不收起 | `resize_quiet_ms` |

不覆盖：`Text`／`Treeview`／`Listbox` 内部滚动仍按行走（它们由控件自身的 `yview_scroll` 处理）；卡片没有悬停态，不做渐变。
