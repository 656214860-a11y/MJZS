# UI 组件契约

本文件定义项目可复用 UI 组件的唯一写法。组件的颜色、间距、圆角和字体均引用 `design_tokens.md`；页面不得自行变体。

## 主按钮

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.primary` |
| 文字 | 白色 |
| 边框 | 无可见边框：1px `solid` 取 `color.primary` 自身底色；仅键盘焦点时为 `color.focus` |
| 圆角 | `radius.md` |
| 字体 | `font.body`（10pt），不再用 11pt bold |
| 尺寸 | 视觉高度 `CONTROL_HEIGHT`（32px）；水平内边距 `space.md`、垂直 `space.xs`；Tk 实测 33px（32±2，见下） |
| 悬停 | 背景 `color.primary.subtle`，文字 `color.primary` |
| 禁用 | 背景 `color.border.default`，文字 `color.disabled.text` |
| 焦点 | `focuscolor` = `color.focus`，1px 焦点边框 |

用于页面的首要、提交、确认动作；同一操作组最多一个主按钮。需要比主按钮更醒目的花钱步骤（如“MCP 优化”）用 `Highlight.TButton`（更深一档的 `color.primary.pressed`），不使用橙色。

**唯一样式来源（UI 批次 2）**：`ui_widgets.setup_styles()` 是按钮、输入框、下拉框、数值框与焦点样式的唯一定义处（按钮在 `_install_button_styles()`，输入在 `_install_input_styles()`）；`ui_theme.apply()` 只安装主题、选项库、滚动条与窗口策略，末尾调用 `setup_styles()`。页面不得再用 `ttk.Style` 配置同名样式，也不得另建局部 Style。

**32px 怎么来**：Tk 的 ttk 控件没有 height 属性，控件高度 = 字体行高 + 2×上下内边距 + 主题边框/焦点占位。10pt 微软雅黑 UI 在 100% DPI 下 `linespace=19px`；按钮沿用 `(space.md, space.xs)` 内边距，`19 + 2×4 + 6 = 33px`。输入类用 `CONTROL_PADDING_Y = space.xs + space.xs//2 = 6px`，`19 + 2×6 + 2×1 = 33px`。两者都落在 32±2px；`tests/test_ui_style_engine.py` 用真 Tk 根窗口实测 `winfo_reqheight()`，非 100% 缩放按 `tk scaling` 折算。

**扁平规则（UI 批次 2 返工）**：按钮常态不画可见边框、不使用 raised 浮雕。clam 主题的 1px `solid` 边框统一用按钮自身底色绘制（`bordercolor`／`lightcolor`／`darkcolor` 同底色，`BUTTON_BORDER_WIDTH`），所以导航、侧栏与主区动作按钮看起来与改前一样扁平；只有键盘焦点状态把同一边框映射为 `color.focus`。禁止再把 `TButton` 基样式或 `Nav.TButton`／`ProjectAction.TButton` 设成可见边框或 raised；`ProjectAction.TButton` 的字号／内边距仍由 `Desktop.fit_sidebar()` 单独紧缩，但不得改颜色与边框。

**唯一例外**：侧栏可用高度低于 `DESKTOP_LAYOUT['compact_below']` 时，`Desktop.fit_sidebar()` 会只缩小 `Compact.TButton`／导航按钮／`ProjectAction.TButton` 的字号与纵向内边距，以便 14 个阶段仍可见；它不定义颜色、背景或焦点色，窗口回到常规高度后仍以本入口的 32px 规则为准。

## 次按钮

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.background.card` |
| 边框 | 无可见边框：1px `solid` 取 `color.background.card` 自身底色；仅键盘焦点时为 `color.focus` |
| 文字 | `color.text.primary` |
| 圆角 | `radius.md` |
| 字体与尺寸 | 同主按钮：`font.body`、高度 `CONTROL_HEIGHT`、水平内边距 `space.md` |
| 焦点 | 1px `color.focus` 焦点环（常态无可见边框） |

用于次要、返回、刷新等不应抢占主动作视觉层级的操作。

## 卡片

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.background.card` |
| 边框 | 1px `color.border.default` |
| 圆角 | `radius.lg` |
| 内边距 | `space.lg` |

卡片承载一个完整的信息或操作单元；同一卡片内的标题、正文与辅助文字分别使用对应字体 token。

## 输入框

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.background.card` |
| 边框 | 1px `color.border.default` |
| 圆角 | `radius.md` |
| 内边距 | `padx=space.md`，`pady=CONTROL_PADDING_Y`（6px） |
| 尺寸 | 视觉高度 32px（`19px 行高 + 2×6px + 2×1px 边框 = 33px`，32±2） |
| 焦点 | 边框 `color.focus` |
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

标准 `ttk.Scrollbar` 的唯一视觉入口是 `ui_theme.apply()`：页面只声明方向和 `command`，不得给单个滚动条创建局部 Style 或内联视觉参数。表格优先由 `DataTable` 承载其横、纵滚动条。

## 文案与复制

`prompt_window.copy_text()` 是应用文本写入系统剪贴板的唯一入口：它用 `clipboard_lock` 串行化跨进程写入，失败返回可展示的原因；页面必须据此给出成功或失败状态，不能静默吞掉。`copy_preview()` 仅用于状态栏回执，会掩盖疑似凭据；复制到剪贴板的原文不被改写。固定动作术语使用“已复制…”与“复制失败：…”，避免页面自行创造不可检索的反馈文案。

## 忙碌／加载态

`ui_widgets.BusyState` 是主后台任务的加载态入口：调用方开始时传入状态文案和需要暂时禁用的控件，收尾时必须用同一对象恢复。组件只管理状态栏、进度条和控件状态，不拥有线程、任务队列或取消语义；自动任务和专用中断链保留既有编排入口。

## 下拉框

业务页必须通过 `SelectBox` 创建下拉框（继承 `ttk.Combobox`）。默认只读，选项自适应宽度封顶 28、弹出列表默认 12 行；可编辑框显式传 `state="normal"`。动态选项更新用 `set_values(values)`，需要保持显式布局宽度时传 `refit=False`；保留 textvariable/current/get 语义。`SelectBox` 固定套用 `Tokens.Combobox.TCombobox`，控件高度与 `TEntry`／`TSpinbox` 同档（32±2px）；`TCombobox` 基样式只作默认继承，不是页面入口。所有下拉框由 `ui_widgets.setup_styles(root)` 作为唯一样式入口。字段、只读态、弹出列表、字体、边框与内边距使用 `design_tokens.md` 的 `combobox.*` token；页面只负责选项、数据绑定和必要的内容宽度，不得复制颜色或字体配置。

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

普通弹窗经 `ui_theme.install_window_placement` 首次定位时，宽高不超过主窗口；随后允许用户缩放，不以主窗口大小作为永久上限，也不沿用业务页面的固定大小或最小尺寸。仍遵守系统桌面尺寸限制；无边框提示层、贴片不属于可缩放对话框。

弹窗最小尺寸由 `DIALOG_MIN_WIDTH`（240px）×`DIALOG_MIN_HEIGHT`（160px）兜底：至少并排放得下两个 96px 按钮＋12px 间距＋两侧 16px 留白（约 236→240），高度至少容下标题、两行说明和底部动作区。定位时只允许缩到这两个下限，不再降到 1×1。

## 窗口尺寸

主窗口首次尺寸由 `DESKTOP_LAYOUT['default_width']`×`DESKTOP_LAYOUT['default_height']` 决定，默认 1280×800；最小尺寸 `min_width`×`min_height` 为 800×600。屏幕可用区更小时，`ui_theme.main_window_size()` 按 `window_margin_x`（24px）／`window_margin_y`（48px）收缩，返回值永不超过可用区；用户之后仍可自由缩放。`desktop.Desktop.__init__` 与 `ui_theme.install_window_placement` 共用这组 token，不各写一套数字。

## 表格

新建表格必须使用 `ui_widgets.DataTable`，由它统一滚动条、空态、列标题、选择回调与通用文字排序；页面仅传入 `(字段名, 标题, 宽度)` 列定义，并保留领域专用的复选、单元格点击及内容自适应逻辑。历史 `ttk.Treeview` 按独立轮次迁移，禁止在业务页复制滚动条或空态实现。

需要空列表仍展示列头时传入 `empty_text=''`，由组件禁用覆盖标签；默认空态文案和其他页面行为不变。剧本准备的三个分类标题始终保留，文件行仍按内容压缩高度。

## 复用规则

每个组件只能有以上一种写法。新增页面必须复用既有组件实现或先扩展本契约；不得在页面内复制、修改样式参数形成第二种写法。

`Toplevel` 弹窗与普通页面遵循完全相同的 token 和组件规则：标题、内容区、输入框和操作按钮均不得退回通用 ttk 样式。主按钮悬停为浅主色底加主色文字；次按钮悬停同样保持可读的主色文字。
