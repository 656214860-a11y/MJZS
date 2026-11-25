# R1776 UI 现代化诊断（结构治理轮·只读诊断）

本轮属于 AGENTS.md §3.3 结构治理轮的「只读诊断」子场景（用户 2026-10-21 指定），写入边界按 §3.5：未改任何 `.py`，未改用户数据，仅新增本结果文件。
测试：按 §5 只读诊断默认不跑测试；本轮未运行测试，也未跑实机截图。基线 HEAD `bdd48715`（master）。日期：2026-10-21。
轮次：R1776 由本轮经 `round_claim.py next` 领取（计数器 last_claimed 1775→1776）。注意：同日「项目状态交接」会话的未提交改动注释里写了「R1776」（剧本准备文件表合并），那是它开工时按状态页轮次头预填的号，并未领取；它提交前应重新领号。
未做：不提交、不改状态页轮次头（该会话工作区同样会改它，避免冲突，留给提交方）。

## A 结论

界面显得「土」的主因不是单点配色，而是**四件事叠加**：

1. **没有层级**：几乎所有按钮同为浅蓝底深蓝字（`TButton`／`Compact.TButton`／`Asset.TButton`／`ProjectAction.TButton` 共用 `secondary` 配色），主次动作只靠少数 `Primary.TButton` 区分；页面底色、卡片底色、容器底色近似同一片灰白，层次靠 1px 灰线硬分。
2. **没有圆角、没有真悬停反馈**：`RADIUS` 令牌（4／8／12）已登记但**全库零消费**；按钮悬停只换一格底色，且 `Primary` 悬停会翻成「近白底＋蓝字」（见 D-1）；表格行、侧栏项无悬停态。
3. **状态反馈粗糙**：底部常驻一条淡绿信息栏＋常驻 0% 进度条；加载只有「状态栏文字＋不确定进度条＋禁用控件」；空态是一行灰字；错误提示 58 处 `notify()` 调用的函数默认 `modal=True`，会弹 Windows 原生 `messagebox`，与应用风格完全脱节。
4. **密度契约把「留白」锁死了**：R1689 裁决「平静、专业、密集」，控件定高 32px（`test_ui_style_engine` 实测 ±2），页面内边距 14／8，侧栏固定 154px。要对标 X 的呼吸感，必须先由用户重新裁决这条契约。

**不是**需要重写的项目：令牌体系、组件唯一出口（`ui_widgets`）、内联 hex／padx 棘轮门禁都已就位，现代化可以几乎全部落在 `ui_tokens`＋`ui_widgets`＋`ui_theme` 三个文件里，业务页基本不用动。真正的技术天花板是 Tkinter 本身（见 I）。

## B 证据与范围

读取：`ui_tokens.py`（274 行）、`ui_theme.py`（380 行）、`ui_widgets.py`（`setup_styles`／`_configure_button`／`DataTable`／`SelectBox`／`LineInput`／`TextArea`／`NotificationDispatcher`／`BusyState`／`ContextMenu`／`Card`／`BaseDialog`／`Tooltip`）、`desktop.py` 的 `_build_sidebar`、主窗口装配与状态栏样式（约 150–340 行）、`desktop_layout.py` 的滚轮处理、`desktop_writing_page.py` 的文件表、`design_tokens.md`／`ui_components.md` 目录、`tests/architecture/test_token_boundary.py`。
Grep 统计（生产模块，排除 tests）：内联 `#rrggbb` 字面量集中在宠物模块（`pet_ui_support.py` 23、`pet_ui.py` 1）；`ttk.Treeview(` 直接构造 4 处／3 文件，`DataTable(` 17 个文件使用；`ScrollForm(` 2 处；`wraplength=<数字>` 51 处；`notify(` 调用约 58 处、显式 `modal=True` 15 处；`CellHover` 在 8 个文件出现。
未做：未启动应用、未截图、未做 DPI／缩放实测。所有「观感」结论来自代码与令牌推断，需第一批落地后用 `scripts/ui_snapshot.py` 截图复核。

## C ui_tokens.py：间距、颜色、字体、圆角

- **颜色**：整套是 Tailwind 灰蓝（`#F7F8FA` 页底、`#FFFFFF` 卡片、`#E5E7EB` 描边、`#2563EB` 主色），本身干净，对比度已按 4.5:1 校过。问题是**语义层缺失**：只有 `background_primary`／`background_card` 两档面，没有「抬升面」「悬停面」「按下面」「描边弱／强」的完整梯度；`secondary_hover`（`#BFDBFE`）、`secondary_pressed`（`#93C5FD`）登记后**没有任何生产代码消费**（见 D-2）。
- **令牌外的硬编码**：`ui_theme.py:54` Treeview 底色写字符串 `'white'`；`ui_theme.py:47` `padding=(8, 4)`、`:56` `padding=8`、`:60` `padding=(14,9)`、`:133` `padding=(2,3)`、`:49` `rowheight=24`；`ui_tokens.py` 里 `SCROLLBAR_THUMB`／`SCROLLBAR_THUMB_ACTIVE`／`SCROLLBAR_ARROW` 三个 hex 不在 `COLORS`（权威文件有豁免，但外观上形成第二套调色板）；`DESKTOP_LAYOUT['sidebar_padding']=6`、`body_padding=(14,…,14,…)`、`PET_LAYOUT` 多处裸数字。
- **间距**：4 / 8 / 12 / 16 / 24 / 32 的刻度合理，但**实际页面用得最多的是 xs(4)／sm(8)**，大块留白（xl／2xl）几乎只出现在弹窗。页面外边距 14／8、行距 1～2px、导航项 `pady=2`，整体是「表单软件」的密度。
- **字体**：全站 `Microsoft YaHei UI`，正文 10pt、标题 14／16 加粗、说明 9pt；层级只靠「大小＋粗细」两档，**没有字重中间档、没有行高（linespacing）规格**；`FONTS['hint']` 用斜体，而中文斜体是系统合成倾斜，观感发虚（生产代码仅 1 处消费，可直接废弃）。
- **圆角**：`RADIUS = {sm:4, md:8, lg:12}` 全库零消费。设计文档强制规则第 3 条「所有圆角必须取自 radius.*」目前是空约束——因为 `clam` 主题画的所有控件都是直角。
- **层次（阴影／分隔）**：无。卡片 `Tokens.Card.TFrame` 是白底＋1px 实线（`ui_widgets.py:1246` 一带），`Box.TFrame`（`ui_theme.py:74`）却是**与页面同色**的底＋`border_strong` 实线——两种「卡片」都靠硬边框，没有「白卡片浮在淡灰底上」的色阶差。

## D ui_widgets.py：按钮、卡片、输入框、表格

- **D-1 主按钮悬停反色**：`ui_widgets.py:91-94` 的 `Primary.TButton`／`Tokens.Primary.TButton` 没有传 `active_background`／`pressed_background`，落到 `_configure_button` 默认值（`:26-28`：悬停底 `primary_subtle #EFF6FF`、悬停字 `primary #2563EB`）。结果是：蓝底白字的主按钮一悬停就翻成**近白底蓝字**，像被「禁用／选中取消」，而不是常见的「加深一档」。这是 9+3 处使用的主按钮的实际体验。只有 `Send.TButton`、`Selected.*`、`Highlight.TButton` 单独写了加深色。
- **D-2 悬停色阶没接线**：默认 `TButton`（浅蓝底）悬停变成**更浅**的 `#EFF6FF`，按下无反馈（无 `pressed_background`）。已登记的 `secondary_hover`／`secondary_pressed` 正是为此准备，却无人使用。
- **D-3 按钮无层级梯度**：同层按钮样式 12 种，但页面里大量按钮（含「刷新」「删除」「中断」「下载文件」）统一是浅蓝底；缺少「幽灵／描边按钮」「文字按钮」「图标按钮悬停底」三档，导致一行 5～6 个按钮视觉权重全等。`Tokens.Secondary.TButton` 是白底，但无描边也无悬停描边，直接融进白卡片。
- **D-4 输入框**：1px `#E5E7EB` 实线、内边距 12×6、聚焦只换边框色（`ui_widgets.py:168` 一带）。没有聚焦外发光／加粗，没有悬停边框加深，`TCombobox` 的箭头仍是 `clam` 方块箭头按钮；下拉弹出列表是原生 `tk.Listbox`（`:197-201` 靠 option database 改色），无内边距、无悬停高亮。
- **D-5 表格**：`Tokens.DataTable.Treeview` 白底、行高 24、无斑马纹、无行分隔弱线、**无悬停行**；选中色 `selection_bg #DBEAFE`。表头 `header_bg #F3F4F6` 加 padding 8，较厚重。`DataTable` 已有自动隐藏滚动条，但滚动条本身仍是 `clam` 样式（带上下箭头钮、宽度默认 ~14px）——这正是用户图 1 红框里「下拉框太丑」的东西（侧栏的已在另一会话未提交改动里去掉）。
- **D-6 卡片**：`Card`（`ui_widgets.py:735`）全库仅 37 处出现，且是直角＋硬边框＋统一 16px 内边距；没有「标题＋内容」「可点击卡片」「选中卡片」变体。
- **D-7 Tooltip**：白底、1px 灰边、无阴影、无淡入，延迟 400ms，功能没问题，视觉偏「系统默认」。
- **D-8 右键菜单**：`ContextMenu` 包的是原生 `tk.Menu`（`ui_theme.py:28-30` 只改了底色／字色），Windows 上是旧式直角菜单，无图标、无悬停圆角——**这是最难现代化的一块**（见 I）。
- **D-9 图标**：`ICON_FONT = Segoe MDL2 Assets` 仅登记了 2 个字形（文件夹、删除，`ui_tokens.py` 末段）；侧栏、按钮基本无图标，只有文字＋少量符号字符（如标题旁的 `✦`、`⚙`）。

## E desktop.py 与各页面：背景、拥挤度、滚动

- **大面积底色**：窗口底 `#F7F8FA`，页面画布 `bg=COLORS['background_primary']`（`desktop.py` 画布创建处），内容区 `ttk.Frame` 无自己的底色；卡片白底落在近白的灰上，差只有 8 个亮度点——**看起来像一整片纯灰白**，没有「白卡片浮起」的层次。
- **侧栏**（`desktop.py:150-205`）：固定宽 154、13 个全宽文字按钮 `pady=2`，当前页是**整条实心蓝底白字**，无左侧指示条、无图标、无分组标题（只有一条 `ttk.Separator`）；「+ 新建项目」「打开项目目录」是两个同权重的浅蓝大块；项目列表是一个 3 行的 `ttk.Treeview`（`Project.Treeview`，行高 24）塞在侧栏里，层级弱。
- **顶栏**：左 16pt 粗体页标题＋右侧小号灰字状态／模型，口号 `✦ 把灵感变成故事` 用 `Muted.TLabel`；宠物贴片叠在标题栏右上角（`pet_layer`）。信息密度高，没有明确的「页面标题区」留白。
- **底栏**：`desktop.py:232` 的 `ttk.Progressbar`（determinate，空闲也在 0%）＋`:247` 的 `PaleGreenHint.TLabel`（淡绿底）。淡绿是「就绪」常驻色，用户每时每刻都看到一整条绿色横幅；执行中变淡蓝、失败变淡红（`:322-326`），三态只换底色，没有图标／强调条。
- **页面布局**：`padx/pady` 数字写死的文件由 `test_token_boundary.PADDING_BASELINE` 冻结（`keyframe_comfy.py` 36、`asset_detail.py` 21、`asset_reference_images.py` 18、`agent/prompt_optimizer.py` 16、`white_model.py` 12、`workflow_settings.py` 11 等）——这些页面不吃令牌，调整留白时不会跟着变。
- **滚动**：`desktop_layout.py:281-336` 的滚轮处理是 `yview_scroll(steps, 'units')` 整步跳，无惯性、无平滑；整页滚动条已有意隐藏（`page_scrollbar=None`），页内局部滚动条仍是 `clam` 款。生硬感来自「整步跳＋看不到位置」两点叠加。
- **启动画面**：深色底（`SPLASH_BACKGROUND #0F172A`）＋青紫强调色，进入应用后瞬间切到浅色界面——品牌色没有延续进主界面。

## F 交互体验：加载态、空态、错误提示

- **加载态**：`BusyState`（`ui_widgets.py:618`）= 状态栏文字＋进度条 `start(15ms)`＋禁用控件。没有骨架屏／局部旋转指示／按钮内「处理中…」态，也没有光标变化（`cursor=` 在 `ui_widgets.py`／`responsive_ui.py` 中 0 处，`desktop.py` 3 处）。长任务期间用户看到的是「底部一根在动的条」和一堆灰掉的按钮。
- **空态**：`DataTable` 默认 `ttk.Label(text='暂无数据', style='Muted.TLabel')` 纯灰字（`:286`）；各页文案是「暂无资产」「暂无镜头」「尚无可用文件」，无插画／图标、无下一步按钮。剧本准备页还特意传 `empty_text=''` 只留列头。
- **错误提示**：两条路径并存——① 状态栏变淡红；② `notify(parent, …)` 函数默认 `modal=True`（`:604`）→ 原生 `messagebox`。`NotificationDispatcher` 类本身默认 `modal=False`，所以风险集中在模块级 `notify()` 的约 58 处调用；其中逐处是否显式传 `modal=False` **本轮未逐一核对**。原生对话框字体、按钮、图标都是系统样式，是全应用最「土」的一个瞬间。
- **成功反馈**：`success` 与 `info` 同走 `showinfo`／状态栏，没有轻量 toast；复制成功等微反馈只写状态栏文字。
- **焦点与键盘**：有焦点环（`focuscolor`）、有 `ShortcutRegistry`、有 Tooltip 的键盘触发——这部分是优点，现代化时不能退化。
- **动效**：无。`ui_theme.py` 文件头直接写着「no image downloads or animation loop」，除启动画面外全应用没有任何过渡。

## G 视觉与交互差距清单

按「用户感知强度」排序，括号内为证据位置：

| # | 差距 | 证据 | 目标观感 |
| --- | --- | --- | --- |
| G1 | 主按钮悬停翻成近白底 | `ui_widgets.py:91-94` 缺 active／pressed 背景 | 悬停加深 `primary_hover`，按下 `primary_pressed` |
| G2 | 默认按钮悬停反而变浅、按下无反馈 | `ui_widgets.py:26-28`；`secondary_hover/pressed` 无人消费 | 浅蓝→稍深→更深三档 |
| G3 | 按钮全员浅蓝底，主次不分 | `ui_widgets.py:82-90` 四个样式同配色 | 主按钮实心、次按钮白底描边、三级文字按钮 |
| G4 | 无圆角 | `RADIUS` 零消费；`clam` 直角 | 按钮／输入／卡片 6–8px 圆角（见 I 的可行路线） |
| G5 | 页面与卡片同属一片灰白，无层次 | `COLORS` 仅两档面；`Box.TFrame` 与页面同色 | 页底略灰、卡片纯白、抬升面再浅一档＋极淡描边 |
| G6 | 滚动条厚重带箭头 | `ui_theme.py:78-81`、`ui_tokens.py` SCROLLBAR_* | 6–8px 细条、无箭头、悬停变宽（侧栏已去滚动条，页内尚未） |
| G7 | 表格无悬停行、无斑马／弱分隔、表头偏厚 | `ui_widgets.py:237-245`；`ui_theme.py:56` | 悬停整行轻着色、行间 1px 弱线、表头去厚 padding |
| G8 | 底部常驻淡绿横幅＋0% 进度条 | `desktop.py:232,247` | 空闲时收起；执行中才出现细进度条；结果用 toast |
| G9 | 原生 messagebox 弹窗 | `notify()` 默认 `modal=True`，约 58 处 | 非阻断错误走应用内 toast／内联提示，仅破坏性确认保留模态 |
| G10 | 空态一行灰字 | `ui_widgets.py:286` | 图标＋一句说明＋一个主操作 |
| G11 | 无加载态局部化 | `BusyState` | 按钮内「处理中…」＋骨架行／旋转点 |
| G12 | 侧栏全宽实心高亮、无图标、无分组 | `desktop.py:172-190` | 左侧 3px 指示条＋浅色选中底、阶段分组标题、线性图标 |
| G13 | 输入框聚焦仅换色，无悬停、Combobox 箭头方块 | `ui_widgets.py:157-202` | 悬停边框加深、聚焦 2px 环；下拉箭头改细线 chevron |
| G14 | 右键菜单、下拉列表是原生直角控件 | `ContextMenu`、`*TCombobox*Listbox.*` | 自绘弹出面板（成本高，列第三批可选） |
| G15 | 留白偏紧（页边距 14／8、导航行距 2、控件高 32） | `DESKTOP_LAYOUT`、`CONTROL_HEIGHT` | 页边距 24／16、控件高 36、卡片内距 16–20（**需先改 R1689 契约**） |
| G16 | 中文斜体、字重只有两档 | `FONTS['hint']`、`FONTS` | 去斜体；补 `medium` 档（微软雅黑 UI 无中间字重，用颜色／字号代替） |
| G17 | 无任何过渡 | `ui_theme.py` 头注释 | 悬停／展开 80–120ms 色彩渐变（仅少数控件，且受 Tk 限制） |
| G18 | 启动画面与主界面断层 | `SPLASH_*` | 启动画面沿用主色与圆角，渐隐进入主界面 |

## H 约束与门禁（现代化时不能踩的线）

1. **R1689 紧凑密度契约**（`design_tokens.md`「控件尺寸与密度」）：`CONTROL_HEIGHT=32`、`test_ui_style_engine` 用真 Tk 实测 ±2。G15 必须先走「契约变更」，同步改文档与断言**阈值的来源常量**，不得弱化断言。
2. **内联常量棘轮**：`test_token_boundary` 冻结每个文件的 hex／数字 padx／pady 计数，只减不增、不许新增文件。新样式必须先进 `ui_tokens`／`COLORS`。
3. **唯一定义处**：按钮／输入／下拉／微调框样式只许在 `ui_widgets.setup_styles()`（`_install_button_styles`、`_install_input_styles`）定义，`ui_theme.apply()` 只装主题再调用它。第一批改动应只落这两处。
4. **扁平按钮规则**：常态不画可见边框、不用 raised（`design_tokens.md`）；圆角方案不得回退为浮雕边。
5. **主色单一**：主色只有蓝色一套，橙／琥珀不作按钮或强调底（已删除）。
6. **测试面**：`tests/` 下 `test_ui_*`、`test_ui_batch3–9_*` 等 28 个 UI 相关文件，另有 `tests/architecture/test_ui_icons_boundary`、`test_migrated_ui_boundaries`。改外观会碰其中的颜色值、样式名、高度断言；样式名（`Tokens.*.TButton` 等）已被页面引用，**不改名只改值**。
7. **启动路径**：禁止递归扫描目录、启动期不加重图片生成（`CLAUDE.md`）。若用 PhotoImage 生成圆角位图，必须懒加载并缓存，勾选图元（`install_tick_indicators`）已有同类「每代保留引用」的坑，可复用其做法。

## I 对标可行性：Tkinter 做到哪一步

Tk（经 ttk `clam`）原生**做不到**：真圆角、阴影、半透明叠加、平滑过渡动画、原生菜单换肤。可选路线：

- **路线 1：纯令牌／样式调整（零新依赖、低风险）**——修悬停／按下色阶、分出按钮层级、拉开面层次、去滚动条箭头、表格悬停行、去底部常驻横幅、toast 取代原生弹窗。预计能解决 G1–G3、G5–G8、G10–G13、G16 的大部分观感问题，**不需要圆角也能明显「变高级」**。
- **路线 2：ttk 图像元素做圆角（中风险）**——本库已有先例：`install_tick_indicators` 用 `style.element_create('DramaTick.indicator','image',…)` 做勾选框。同法可为 `TButton`／`TEntry`／`TCombobox` 生成九宫格圆角 PhotoImage（纯 Python 逐像素 `put`，无 PIL，边缘抗锯齿对已知背景色预混合）。限制：背景色必须已知（卡片内外底色不同要出多套图）、DPI 缩放要按 `tk scaling` 重生、首次生成有成本（要缓存或后台预热）。**本轮未实测随附 Tk 版本对 `-format`／alpha 的支持，第一批之后需要一个 30 行的探针脚本确认。**
- **路线 3：Canvas 自绘控件（高风险、不建议铺开）**——只在「侧栏导航项」「toast」「空态卡片」这类全新且无历史包袱的小部件上用，不替换现有 ttk 控件（会丢焦点环、键盘、可访问性与 28 个测试文件的假设）。
- **不建议做**：换第三方 UI 库（违反零依赖）；全局重写成 `tk.Canvas` 渲染。

推荐：**路线 1 为主，路线 2 仅用于按钮与输入框，路线 3 限于三个新增小部件。**

## J 整改路线（待确认，不自动执行）

每条为独立轮，互不为前置，除非注明；每轮最多改 3 个模块（§3.3），每轮结果文件写明来源「R1776 J-x」。

### 第一批：令牌与基础组件（几乎全部落在 3 个文件，业务页零改动）

- **J1（修复轮）按钮悬停／按下色阶接线**：`ui_widgets.py` 给 `Primary`／`Tokens.Primary` 补 `active_background=primary_hover`、`active_foreground=background_card`、`pressed_background=primary_pressed`；默认 `TButton` 系用 `secondary_hover`／`secondary_pressed`。覆盖 G1、G2，是**全站体感提升最大、风险最小**的一条。
- **J2（功能轮）按钮层级**：新增「描边次按钮」「文字按钮」两个样式名（不改既有名），把「刷新」「删除」「中断」等低权重动作迁移过去（迁移页面按文件分轮，每轮≤3 个）。覆盖 G3。
- **J3（功能轮）面层次令牌**：`COLORS` 增加 `surface`（抬升面）、`surface_hover`、`border_subtle`；`Card`／`Box.TFrame`／`Treeview` 底色改取令牌，去掉 `ui_theme.py:54` 的 `'white'` 与裸 padding。覆盖 G5，兼清 C 中的令牌外硬编码。
- **J4（功能轮）滚动条与表格质感**：`ui_theme.py` 重建 `TScrollbar` 布局去箭头、收窄；`DataTable` 加悬停行、弱行线、薄表头。覆盖 G6、G7。
- **J5（功能轮）输入框与下拉**：悬停边框、聚焦环加粗、Combobox 箭头换 chevron、Listbox 内边距。覆盖 G13。
- **J6（契约轮，需用户裁决）更新 R1689 密度契约**：把 `CONTROL_HEIGHT` 32→36、页边距与卡片内距上调一档，同步 `design_tokens.md`、`ui_components.md`、`test_ui_style_engine` 常量来源。覆盖 G15。**不得与 J1–J5 同轮**。
- **J7（探针，只读）圆角可行性**：写一个独立探针脚本（放 `维护记录/基准脚本/`），在随附 Python／Tk 上实测 `element_create('image')` 九宫格按钮的绘制、DPI 缩放与首次生成耗时。结论决定第二批是否做 G4。

### 第二批：布局

- **J8（功能轮）侧栏改造**：左 3px 指示条＋浅色选中底、阶段分组小标题、线性图标（沿用 Segoe MDL2，新增字形只进 `ui_tokens`）、「新建项目」做成主操作、项目列表去 3 行 Treeview 框感。覆盖 G12。`desktop.py` 只改 `_build_sidebar` 附近。
- **J9（功能轮）底栏与反馈条**：空闲时收起进度条与「就绪」绿条，执行中显示细进度条，结果走 toast。`desktop.py` 的 `status_label`／`progress` 装配＋`sync_status_style`。覆盖 G8。
- **J10（功能轮）toast 组件 + notify 改道**：`ui_widgets.py` 新增 `Toast`（路线 3 的小部件），`NotificationDispatcher` 的非阻断 error／warning／success 默认走 toast，保留 `modal=True` 给破坏性确认；逐个核对 58 处 `notify(` 调用。覆盖 G9。
- **J11（功能轮）空态组件**：`ui_widgets.py` 新增 `EmptyState(icon, text, action)`，`DataTable` 空态可选使用，先迁 3 个页面。覆盖 G10。
- **J12（结构治理轮·执行）高频页面的数字 padx／pady 迁令牌**：按 `PADDING_BASELINE` 由大到小，每轮一个文件（`keyframe_comfy.py` 36 → `asset_detail.py` 21 → …），并下调棘轮基线。让 J6 的留白调整真正覆盖这些页面。
- **J13（功能轮）页面留白与标题区**：在 J6 通过后，调整 `DESKTOP_LAYOUT.body_padding`、顶栏标题区、口号位置。覆盖 G15 的页面部分。

### 第三批：微交互

- **J14（功能轮）加载态局部化**：`BusyState` 增加「按钮内处理中…」与光标 `watch`；长任务列表用占位行代替整页禁用。覆盖 G11。
- **J15（功能轮）轻量过渡**：仅对侧栏项、按钮、Toast 做 80–120ms 色彩渐变（`after` 逐帧插值，帧数封顶、离屏时不跑），受 J7 探针结论约束。覆盖 G17。
- **J16（功能轮）启动画面衔接**：启动画面沿用主色与圆角，进入主界面时渐隐。覆盖 G18。
- **J17（可选，高风险）自绘右键菜单**：只有在 J1–J16 后用户仍觉得原生菜单突兀时再评估。覆盖 G14。
- **J18（功能轮）滚动手感**：滚轮步长按像素折算、加极短缓动；评估后再决定是否做。覆盖 E 中滚动项。

### 建议执行顺序

J1 → J3 → J2 → J4 → J5 → J7（得出圆角结论）→ **用户裁决 J6** → J8 → J9 → J10 → J11 → J12／J13 → J14 → J15 → J16。J17／J18 可选。

## K 测试计划

只读诊断本轮不改测试。确认 J 后，各条对应的测试动作（均为**新增或同步值，不弱化断言**，结果文件写「断言未动」）：

| J | 测试动作 |
| --- | --- |
| J1 | 在 `test_ui_style_engine.py` 或 `test_ui_widgets_inputs.py` 新增表驱动用例：遍历全部 `*.TButton` 样式，断言 `style.map` 中 `active`／`pressed` 背景都存在，且主按钮悬停背景 ≠ `primary_subtle`、亮度低于常态；防止再次出现「悬停变浅」 |
| J2 | `test_button_boundary` 登记新样式名；新增「迁移后页面不再引用已降级的按钮样式」检查 |
| J3 | `test_ui_token_contract` 增加新令牌的存在性与对比度（文字 vs `surface` ≥ 4.5:1）；`test_token_boundary` 的 hex 基线不增 |
| J4 | `test_ui_widgets_table.py` 增加悬停行 tag 与弱行线断言；`test_ui_theme.py` 断言滚动条布局不含箭头元素、宽度令牌生效 |
| J5 | `test_ui_widgets_inputs.py` 增加悬停／聚焦态 `bordercolor` 映射断言；高度仍 32±2（或 J6 后新值） |
| J6 | `test_ui_style_engine.py` 的高度常量改读 `CONTROL_HEIGHT`（目前同源，改令牌即同步），文档与测试一同变更，**契约轮**走全量自检 |
| J7 | 探针脚本自带自检，不入 `tests/`；结论写入结果文件 |
| J8 | `test_ui_batch3_shell.py`、`test_desktop_compact_layout.py`、`test_ui_edges.py` 同步侧栏结构断言；新增「窗口最小 800×600 下 13 个导航项仍可滚动到达」用例 |
| J9–J11 | `test_ui_notifications.py` 增加「非破坏性 error 不触发原生 messagebox」「破坏性确认仍模态」；`Toast`／`EmptyState` 各加构造、销毁、重复触发不泄漏 `after` 回调的用例 |
| J12 | 每轮下调 `PADDING_BASELINE` 对应文件计数 |
| J14–J16 | 增加 `after` 回调在窗口销毁时被取消的用例（沿用 `ui_theme.cancel_position_job` 的写法）；动画帧数封顶断言 |

验证按 §5：UI 外观轮用 `smoke_test.py` ＋ `run_selftests.py -k ui_` 定向，涉及令牌／分层时加 `--architecture`；每个批次结束跑一次 `scripts/ui_snapshot.py` 截图留档（改前改后各一张，便于肉眼对比）。J6 与 J10 属跨层契约改动，按 §5 跑全量安全自检。

## L 风险与限制

- 本轮**未启动应用、未截图、未跑任何测试**；「观感」判断来自代码，可能与实机在不同 DPI／缩放下的表现有偏差。
- 页面级统计（`wraplength` 51 处、`notify` 58 处等）是 grep 口径，不含动态拼接；`notify` 逐处 `modal` 取值未核对。
- 圆角方案（路线 2）的可行性**未实测**，尤其是随附 Python 3.15.0a2 的 Tk 构建对 PhotoImage alpha 的行为；J7 探针之前不要承诺 G4。
- 没有扫完的页面：`keyframe_comfy.py`、`asset_detail.py`、`white_model.py`、`workflow_settings.py`、各设置窗等「自己写 padx／pady」的页面未逐个看视觉，仅从棘轮基线推断为留白不受令牌控制。
- 现代化会触碰 28 个 UI 测试文件，其中不少断言了具体色值和高度；J1–J5 均为「改值不改名」，预期红点集中在颜色断言，需要同步而非放宽。
- 并行风险：另一工作区「项目状态交接」有未提交的剧本准备页和侧栏滚动条改动（`desktop.py`、`responsive_ui.py`、`desktop_writing_page.py`、`ui_tokens.py`），第一批若碰 `ui_tokens.py`／`desktop.py` 须等它先提交，避免合并冲突。

## M 完成状态

只读诊断完成（令牌、基础组件、主窗口与页面、交互体验四个范围＋18 项差距清单＋18 条分批整改路线＋测试计划）。未改任何 `.py`、测试、配置、用户数据与既有结果文件；仅新增本报告；未提交、未改状态页轮次头。下一步由用户确认 J 中要执行的条目（建议先做 J1、J3、J2，并裁决 J6 是否放宽 R1689 密度契约）后，再逐条立执行轮。
