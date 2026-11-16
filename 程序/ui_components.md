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

`ui_widgets.NotificationDispatcher` 是错误、警告、成功与一般提示的唯一分发入口。调用方只提供业务文案、级别和是否需要模态提示；分发器先更新既有状态栏，模态提示仍复用 Tk 的 `messagebox`，不另建第二套窗口。新建页面不得直接组合 `status.set()` 与 `messagebox.show*()` 表达同一结果；历史页面按独立轮次迁移。

**错误策略（R1689 裁决，UI 批次 2 落地）**：可恢复的错误（网络、模型、校验）默认非模态——`NotificationDispatcher.error()` 默认 `modal=False`，只把完整文案落到状态栏，不弹系统框、不锁界面；需要“查看详情／重试”的页面自行在动作附近提供。只有删除、覆盖等破坏性确认保留模态，但它们走 `ConfirmDialog`／`ask_confirmation`，不在本函数内。仅当后续代码确实必须等用户关掉提示才能继续时，调用方才显式传 `modal=True` 并写明理由。状态栏颜色按级别区分（就绪中性、成功绿、警告、错误红），不再一律绿色。

## 右键菜单

`ui_widgets.ContextMenu` 是右键菜单的构建、定位和 grab 释放入口。页面只声明菜单项与领域回调；历史菜单按独立轮次迁移。

## 文件／目录选择

`ui_dialogs.FileDialog` 是文件与目录选择的唯一入口。页面只传入标题、初始目录和类型；取消统一返回空元组，窗口打开失败通过既有 `NotificationDispatcher` 显示可见错误。历史直接 `filedialog` 调用按独立轮次迁移。

## 快捷键

`ui_shortcuts.ShortcutRegistry` 是页面快捷键的登记入口。页面以稳定的作用域、语义名称和 Tk 序列注册快捷键；同一作用域的规范化重复序列会立即拒绝，以便集中审计冲突与后续帮助提示。历史直接 `bind()` 按独立轮次迁移。

## Tooltip

`ui_widgets.Tooltip` 是截断名称或图标含义等短说明的唯一浮层入口。页面传入目标控件和完整说明即可；组件统一 400ms 延迟、鼠标悬停与键盘焦点触发，以及离开、失焦、销毁时的取消与清理。Tooltip 不取得焦点或 grab，不能承载操作按钮、表单或长篇说明；后两类分别使用既有弹窗或 `DescriptionBlock`。

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

## 复用规则

每个组件只能有以上一种写法。新增页面必须复用既有组件实现或先扩展本契约；不得在页面内复制、修改样式参数形成第二种写法。

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
