# R1710：结构治理轮·执行（UI 批次 2）——样式引擎收口

> 执行者：DeepSeek Harness（headless 子轮）。**未领轮次、未改 `project_status.md`、未执行任何 git 写命令、未提交**；轮次号与提交由 Claude 分配／验收。
> 工作范围严格按 `工作流任务/RUI2_taskbook.md` 的「允许改的文件」执行：`ui_theme.py`、`ui_widgets.py`、`ui_tokens.py`（新增必要令牌）、`ui_components.md`、`design_tokens.md`、`desktop.py`（仅窗口默认尺寸一行）、`tests/` 本批测试、本结果文件、`工作流任务/probe_ui2/`。`app.py` 曾试改后**已原样还原**（`git diff -- 程序/app.py` 为空）。

## §7 三问

1. **本轮属于 §3 哪种类型？** 结构治理轮·执行（UI 批次 2，样式引擎收口）。不改功能、不改用户数据、不改页面使用的样式名。
2. **测试跑了吗？三个基线过了吗？** 跑了。默认冒烟 **8/8**；受影响冒烟 **9/9**（门禁 68 秒、0 红）；定向主命令 **125 条中 124 条通过、1 条既有用例红**（`test_video_ui`，见 D-2）；架构门禁 **368 条中 366 条通过、2 条红**（均为并行任务文件导致的既有红，见 B-4）。**全量安全回归未跑**（任务书明确禁止）。
3. **`project_status.md` 的欠账少了吗？** 没有。本轮按任务书不写状态页；改源码，Claude 提交时应计 1 个源码轮的全量欠账。

## A 改动

### A-1 文档先行（唯一规则）

- `ui_components.md`：重写主按钮／次按钮／输入框规格；写明 **`ui_widgets.setup_styles()` 是按钮、输入、下拉、数值、焦点样式的唯一定义处**，`ui_theme.apply()` 只装主题并调用它；写明 32px 计算式、焦点 `focuscolor`、错误默认非模态、主窗口 1280×800／最小 800×600、弹窗最小 240×160；把侧栏 `Desktop.fit_sidebar()` 的响应式紧缩登记为唯一例外（只缩字号／纵向内边距，不定义颜色、背景、焦点）。
- `design_tokens.md`：新增 `CONTROL_PADDING_Y`（6px，`space.xs + space.xs//2`）与 32px 计算式；新增「窗口尺寸」表（默认 1280×800、最小 800×600、边距 24／48、弹窗 240×160）；更新 `combobox.padding`、`input.padding`、`input.focus.border`、`combobox.focus`。
- `docs/REQUIREMENTS.md`／`docs/DESIGN.md`：**没有 UI 章节**（逐行 grep 只有阶段级条文中的“界面提示”字样），按任务书只改上述两份 UI 文档，未在阶段文档中新增条目。

### A-2 样式唯一来源

- 选择「把同名样式合并进 `ui_widgets.setup_styles()`，`ui_theme.apply()` 调用它」：
  - 调用点不变：`desktop.py` 仍 `apply_theme(win);setup_styles(win);install_window_placement(win)`；`ui_theme.apply()` 末尾 `from ui_widgets import setup_styles; setup_styles(win)`。
  - `ui_widgets.setup_styles()` 内部按主题缓存（`drama_styles_theme`），`apply()` 后的第二次调用是空操作，不会二次覆盖。
  - 理由：`setup_styles` 是组件构造（`PrimaryButton`／`SecondaryButton`／`SelectBox`／`LineInput`／`DataTable`）实际依赖的入口；调用点已覆盖全部页面，反过来需改更多调用点。`ui_theme` 仍保留主题、TLabel、Treeview、滚动条、进度条、窗口策略等非按钮样式。
- 新增 `ui_widgets._configure_button()`、`_install_button_styles()`、`_configure_combobox()`、`_install_input_styles()` 四个模块级辅助，避免 `setup_styles` 超过 150 行棘轮（当前 setup_styles 约 44 行）。
- `ui_theme.py` 删除：`TButton`、`Compact.TButton`、`Send.TButton`、`Selected.Compact.TButton`、`Asset.TButton`、`Primary.TButton`、`Highlight.TButton`、`Nav.TButton`、`Sub.Nav.TButton`、`Selected.Sub.Nav.TButton`、`Selected.Nav.TButton`、`TEntry`、`TCombobox` 及对应 `map`。**样式名一个未改**。

### A-3 落值

- `ui_tokens.py` 新增：
  - `CONTROL_PADDING_Y = SPACING["xs"] + SPACING["xs"] // 2`（=6）；`COMBOBOX_CONTROL_PADDING = (COMBOBOX_PADDING[0], CONTROL_PADDING_Y)`。
  - `DIALOG_MIN_WIDTH = 240`、`DIALOG_MIN_HEIGHT = 160`（依据见文档：两个 96px 按钮并排＋12px 间距＋两侧 16px 留白≈236；标题＋两行说明＋动作区≈160）。
  - `DESKTOP_LAYOUT['default_width'/'default_height']`（1280／800）、`window_margin_x/window_margin_y`（24／48）。
- 按钮：全部 10pt `FONTS['body']`（`Highlight` 用 10pt `body_bold`，`Tokens.Icon` 用既有 `ICON_FONT`），水平／垂直内边距 `(space.md, space.xs)`，`borderwidth=1`，`focuscolor=COLORS['focus']`，禁用态 `COLORS['disabled_text']`。
- 输入：`TEntry`、`Tokens.LineInput.*`、`TSpinbox` 均 10pt、`(space.md, CONTROL_PADDING_Y)`、1px 边框、焦点边框 `COLORS['focus']`；`SelectBox` 固定 `Tokens.Combobox.TCombobox`（`COMBOBOX_CONTROL_PADDING`），旧 `TCombobox` 基样式保留 `COMBOBOX_PADDING` 仅供默认继承。
- 真 Tk 实测（`tk scaling=1.333…`，100% DPI）：Primary **33px**、Secondary **33px**、`TEntry` **33px**、`LineInput` **33px**、`SelectBox` **33px**、`TSpinbox` **33px**、裸 `TButton` **33px**，全部在 32±2px。
- 计算式：10pt 微软雅黑 UI `linespace=19px`；按钮 `19 + 2×4 + 6（1px 边框＋焦点占位）= 33`；输入 `19 + 2×6 + 2×1 = 33`。未新增 hex，未新增未命名数字常量。

### A-4 窗口策略

- `ui_theme.main_window_size(work_width, work_height)`：`min(默认值, 可用区 − 边距)`，永不超过可用区。
- 主窗口默认 **1280×800**、最小 **800×600**；`desktop.py` 只改 `win.geometry(...)` 这一行（改用 `DESKTOP_LAYOUT['default_*']` 与 `window_margin_*`），初始化顺序未动。
- 弹窗：`place()` 中 `window.minsize(1,1)` 改为 `window.minsize(DIALOG_MIN_WIDTH, DIALOG_MIN_HEIGHT)`；主窗口的最小尺寸收缩逻辑仍保留，弹窗不再被降到 1×1。
- `ui_theme.py` 的 `install_window_placement` 仍为 **224 行**（棘轮上限 224），`desktop.py::__init__` 仍为 **175 行**（上限 175）。

### A-5 错误默认非模态

- `ui_widgets.NotificationDispatcher.error(..., modal=False)` 现为默认非模态；`notify()` 的通用默认未动。
- 实际源码 grep 到 **15 处** `.error()` 调用（任务书写 13 处）：`app.py` 5、`desktop.py` 3、`desktop_idea_chat.py` 3、`desktop_project_pages.py` 2、`desktop_script_pages.py` 2。逐处检查：**没有一处后续代码依赖“用户先关掉弹窗”才能继续**，因此生产调用全部保留默认非模态。
- `app.py`、`desktop_idea_chat.py`、`desktop_project_pages.py`、`desktop_script_pages.py` **不在允许改的文件内**，未改；`desktop.py` 的 3 处调用也不在“仅初始化顺序与窗口默认尺寸”授权内，未改。
- 破坏性确认仍走 `ConfirmDialog`／`ask_confirmation`，未改。

### A-6 测试

- 新增 `程序/tests/test_ui_style_engine.py`（10 条，docstring 写明「UI 批次 2」）：
  1. AST 证明按钮／输入样式只在 `ui_widgets` 定义，`ui_theme` 无同名定义；
  2. `ui_theme.apply()` 调用 `setup_styles`；
  3. 真 Tk 实测 Primary／Secondary／TEntry／LineInput／SelectBox／TSpinbox 33px（按 `tk scaling` 折算，32±2）；
  4. 16 个按钮样式的 `focuscolor == COLORS['focus']`；
  5. `CONTROL_PADDING_Y` 与 `COMBOBOX_CONTROL_PADDING` 的派生关系；
  6. `error()` 默认 `modal=False` 且不弹框，显式 `modal=True` 仍弹；
  7. 默认 1280×800／最小 800×600、`main_window_size` 收缩；
  8. 真主窗口按策略定尺寸并保留 800×600 最小；
  9. 弹窗最小时不再 1×1。
- `程序/tests/test_ui_notifications.py`：`notifier.error("...", modal=True)` 的**调用处**补了 `modal=True`；断言结构、期望文本与比较方式**未动**（该用例名即 “when modal”）。见 D-1。

## B 验证

按任务书顺序执行；工作目录 `D:\漫剧制作助手\程序`，解释器 `D:\漫剧制作助手\运行环境\Python\python.exe -B`。

1. **主定向命令**（任务书原样关键词＋新增文件）：
   `run_selftests.py -k ui_theme ui_widgets ui_tokens ui_token_contract design_tokens video_ui pet_ui_support test_layers function_size_ratchet module_size_ratchet ui_style_engine`
   → **125 条，124 通过，1 红**：`test_video_ui#5 test_the_grey_example_is_refused_at_the_door`（见 D-2）。其余 14 个工作单元全绿；新增 `test_ui_style_engine` 10/10；`test_ui_theme` 15/15；`test_function_size_ratchet` 2/2；`test_layers` 5/5。
2. `smoke_test.py` → **8/8 通过、0 失败**。
3. `smoke_test.py --affected ui_theme ui_widgets desktop` → **9/9 项通过**；门禁 12 个测试文件、68 秒、**0 个文件有红**。
4. `smoke_test.py --architecture`（只跑 1 次）→ **368 条，366 通过，2 红**：
   - `test_round_baselines.test_round_number_continuous`：`1702 != 1706`。树内已有并行任务未提交的结果文件（`tasks_round_1705_result.md` 等）而 `project_status.md` 由 Claude 收尾，非本批文件；本轮不写状态页。
   - `test_unification_ratchet.test_bare_json_load_debt_is_a_nonincreasing_subset`：新增债务 `client_profiles.py:101`、`model_pool.py:873`、`model_pool.py:919`、`workflow_engines.py:167`、`workflow_engines.py:241`。这些是并行「全客户端适配」任务的文件（`client_profiles.py` 为未跟踪新文件），**本轮未碰**。
   - 本批相关门禁（`test_layers`、`test_function_size_ratchet`、`test_module_size_ratchet`、`test_token_boundary`、`test_combobox_boundary`、`test_button_boundary`、`test_input_boundary`、`test_text_component_boundary`、`test_scrollbar_theme_boundary`、`test_ui_icons_boundary` 等）均绿。
5. 定向补充：
   - `run_selftests.py -k ui_theme ui_notifications ui_widgets_inputs ui_widgets_dialogs ui_token_contract` → **42/42**。
   - `run_selftests.py -k function_size_ratchet ui_style_engine ui_theme` → **27/27**。
   - `run_selftests.py -k test_ui_edges test_video_ui`（为 D 节定位既有契约冲突）→ **181 条，178 通过，3 红**：除上面的 `test_video_ui` 用例外，另有 `test_ui_edges` 两条（`test_page_build_failure_reports_instead_of_blank_page`、`test_source_selector_display_snaps_back_when_switch_is_blocked`），原因同为“默认不再弹 `messagebox.showerror`”。详见 D-2。
6. **未运行**：`run_selftests.py --all --safe`（任务书明确要求不跑）、`smoke_test.py --gate`（未在本批验证表中，且跨树 GUI 等待风险已知）。

## C 截图

- 改动前：`D:\漫剧制作助手\工作流任务\probe_ui2\before.png`（1080×740，窗口原点 428,177；默认 1080×740 的旧策略）。
- 改动后：`D:\漫剧制作助手\工作流任务\probe_ui2\after.png`（1280×800，窗口原点 328,147；新策略）。
- 采集脚本：`probe_ui2\show_main.py`＋`probe_ui2\capture_window.ps1`（PowerShell `System.Drawing` 截窗口矩形，零第三方依赖）。探针把 `Desktop.choose_project` 替换为空操作、清空 `_startup_project_choice`，**没有打开任何用户项目、没有读写项目内容**；截图左侧仅显示程序根项目登记的名称列表。
- 目视说明：
  - 窗口从 1080×740 变为 1280×800，正文区更宽更高；同一屏能完整看到项目列表、六个动作按钮与状态栏。
  - 侧栏 14 个阶段与“资产清单”行距变高（按钮从旧内边距变为 10pt＋32px 档），文字未裁切；顶部“我的项目”与内容区对齐保持不变。
  - 按钮边距与高度统一后，底部动作按钮不再出现原先的紧贴／高矮差；主蓝仍为唯一强调色。
  - **未目视验证**：DPI 125%／150%、键盘 Tab 焦点环的实际观感、下拉框弹出列表、真实项目内页；这些不在本批截图中，不能据截图宣称已验收。
  - 宠物层的橙色齿轮仍存在（`pet_ui` 不在本批允许文件内），本批“不保留橙色”只覆盖按钮／主题样式，不能据此说全程序已无橙色。

## D「断言未动」与需裁决事项

### D-1 已做的测试调用调整（断言未动）

- `tests/test_ui_notifications.py`：唯一改动是 `notifier.error("...", modal=True)` 的**调用参数**。该用例名 `test_error_updates_status_and_reuses_error_dialog_when_modal` 本身就是“modal 时”的契约；断言结构、期望文本、被测对象与比较方式均未动。若不补 `modal=True`，该用例会与新的默认值冲突；补参数等价于任务书要求的“调用方显式传 modal=True”。
- 未删除、未弱化、未跳过任何断言；未新增 skip。

### D-2 需 Claude 裁决：3 条既有用例仍断言“错误必须弹系统框”

新默认非模态后，以下 3 条既有用例红；它们要改的**不是本轮允许的文件**，因此按任务书“先不改”保留原样：

| 用例 | 失败点 | 对应生产调用 | 为何未在允许范围 |
| --- | --- | --- | --- |
| `test_video_ui.WritingSheetExampleTests.test_the_grey_example_is_refused_at_the_door` | 期望 `app_module.messagebox.showerror` 被调用 1 次，实际 0 次 | `app.py:646` `notifier.error(str(e), title='无法准备')` | `app.py` 不在允许改的文件内 |
| `test_ui_edges.UiEdgeTests.test_page_build_failure_reports_instead_of_blank_page` | 期望 `messagebox.showerror` 被调用 1 次，实际 0 次 | `desktop.py:1484` `notifier.error(str(exc), title='页面无法显示')` | `desktop.py` 仅授权“初始化顺序与窗口默认尺寸”几行 |
| `test_ui_edges.UiEdgeTests.test_source_selector_display_snaps_back_when_switch_is_blocked` | 期望 `messagebox.showerror` 被调用 1 次，实际 0 次 | `desktop.py:758` `Desktop.safe()` 的 `notifier.error(str(e))` | 同上 |

两种收口方式，请裁决：

1. **按产品裁决改测试期望（推荐）**：这 3 条改为断言状态栏文案（`d.status.get()`／`status` 值）包含对应原因，仍可保留“业务状态不变”的断言。这是“可恢复错误默认非模态”的直接结果。
2. **授权把这 3 处生产调用显式改为 `modal=True`**：需 Claude 修改 `app.py` 与 `desktop.py` 的非授权行；理由只能写成“用户点了按钮但页面/动作没有发生，必须阻断告知”，与任务书“其余用默认”有张力，故执行者不自行决定。

补充事实：逐处检查 15 个生产调用后，**没有一处代码流程依赖“用户关闭弹窗后继续”**；3 条红全部来自既有测试对 `messagebox.showerror` 的断言，不是产品代码依赖。

### D-3 其他需知

- **调用数 13 vs 15**：任务书／审计写 13 处，实际源码 grep 为 15 处（清单见 A-5）。未改任何一处生产调用。
- **`TCombobox` 基样式高度仍为 29px**：既有 `test_ui_theme.test_global_combobox_style_uses_the_design_tokens` 断言 `TCombobox` 的 `padding == '8 4'`，按“不改既有断言”保留；实际页面唯一入口 `SelectBox` 使用新的 `Tokens.Combobox.TCombobox`，实测 33px。若 Claude 决定连基样式也抬到 33px，需要同步改该断言（属契约有意变更，本批未做）。
- **`TextArea`** 是多行控件，仍用 `INPUT_PADDING_Y=8`，不套 32px 单行高度；文档已写明。
- **侧栏响应式紧缩**：`desktop.fit_sidebar()` 在可用高度 < `compact_below` 时仍会改 `Compact.TButton`／导航／`ProjectAction.TButton` 的字号与纵向内边距；它不在本批授权内、未改，文档已登记为唯一例外，且不定义颜色/焦点。
- `docs/REQUIREMENTS.md`／`DESIGN.md` 无 UI 章节，本批只改 `ui_components.md`／`design_tokens.md`。

## E 提交状态

**未提交，由 Claude 验收后提交。** 本轮未执行 `git add/commit/stash/checkout/reset/clean` 等写命令；未改 `project_status.md`、`AGENTS.md`、`architecture.md`、`skills/`、`private/`、`.env`；未删除文件；未新增 `.bak_*`；未引入第三方依赖。

## F 返工（RUI2b，2026-10-19）

### F-1 三问

1. **轮次类型**：修复轮（UI 批次 2 返工，只恢复扁平观感并处理点名红；未新增功能）。
2. **测试跑了吗？三个基线过了吗？** 跑了任务书点名的 1–3；定向 248 条 0 文件红、默认冒烟 8/8、受影响冒烟 9/9（34 条 0 红）。`test_pet_ui` 单次 599 条中 1 红，见 F-4 第 2 条／F-6；不是本轮改动的文件，也不是 ReplyBox 清理偶发红。**未跑** `--architecture` 与 `--all --safe`（任务书明确禁止）。
3. **`project_status.md` 的欠账少了吗？** 没有。按任务书不写状态页、不领号、不提交；本轮改源码，Claude 提交时按既有口径计欠账。

### F-2 改动文件

- `程序/ui_widgets.py`：`_configure_button()` 改为「常态不可见边框＋焦点边框」；显式补 `ProjectAction.TButton` 基样式；其余状态色保持上一轮被验收版本。
- `程序/ui_tokens.py`：新增 `BUTTON_BORDER_WIDTH = 1`（唯一的按钮边框数值，供测试与文档引用）。
- `程序/tests/test_ui_style_engine.py`：新增 3 条扁平/焦点断言；`BUTTON_STYLES` 补 `ProjectAction.TButton`；顶部 docstring 补第 4 条。
- `程序/tests/test_video_ui.py`（仅点名的 `test_the_grey_example_is_refused_at_the_door`）：改为断言同一条错误文本落状态栏、系统模态框零调用，并保留「没有真去准备任务书」。
- `程序/tests/test_ui_edges.py`（仅点名的两处）：`test_page_build_failure_reports_instead_of_blank_page` 与 `test_source_selector_display_snaps_back_when_switch_is_blocked` 改为断言状态栏原文与模态框零调用；回退行为、`show()` 仍抛异常、当前分镜不切换、下拉框回退等断言全部保留。
- `程序/tests/test_pet_ui.py`（仅第 4013 行）：期望 `'white'` 改为 `winfo_rgb(...)` 颜色值比较；该文件其余 R1704 未提交改动（`wait_for_the_reply` 与 6 处 `addCleanup`）一字未动。
- `程序/ui_components.md`、`程序/design_tokens.md`：补「扁平规则」、按钮边框 token 与次按钮焦点环说明。
- `工作流任务/probe_ui2/show_main.py`、`focus_probe.py`、`after2.png`、`after2_focus.png`、`tmp_root/`：探针改用 `tempfile.mkdtemp()` 空项目根。

### F-3 边框根因（实测）

- 上一轮把 `ui_theme.py` 里的同名按钮样式合并进 `ui_widgets.setup_styles()` 时，新的 `_configure_button()` 给**所有**按钮统一写了 `borderwidth=1`，并且没有指定 `relief`；clam 主题的默认 `TButton` `relief` 是 `raised`，`Button.border` 会按 `bordercolor`（clam 默认 `#9e9a91`）、`lightcolor`、`darkcolor` 画 1px 立体边。
- 改前的样式表里：基样式 `TButton` 明确 `borderwidth=0`；`Nav.TButton`／`Sub.Nav.TButton`／`ProjectAction.TButton` 都没有自己的边框，继承基样式的 0；因此是扁平的。上一轮把基样式改成 1 后，导航、`+ 新建项目`／`打开项目目录`（`ProjectAction.TButton` 只覆盖 font/padding，其余继承 `TButton`）和主区动作按钮（`self.button(...)` 用 `TButton`）全部继承了这个 1px raised 边。
- 本轮不靠「把数字改回 0」碰运气：`_configure_button()` 统一 `borderwidth=BUTTON_BORDER_WIDTH`、`relief="solid"`，并把 `bordercolor`／`lightcolor`／`darkcolor` 设成该按钮自己的 `background`；焦点状态再映射到 `COLORS['focus']`。这样常态没有可见边框、没有浮雕，焦点环仍在（真窗截图 `after2_focus.png` 中「02 剧本结构」出现蓝色键盘焦点环）。`ProjectAction.TButton` 也在 `_install_button_styles()` 里显式定义，避免它在 `Desktop.fit_sidebar()` 首次运行前落到 ttk 默认边框。

### F-4 验证（本轮实测）

1. `run_selftests.py -k ui_theme ui_widgets ui_tokens ui_token_contract ui_style_engine design_tokens video_ui ui_edges ui_notifications pet_ui_support test_layers function_size_ratchet module_size_ratchet` → **12 个测试文件、248 条用例、246.3 秒、0 个文件有红，`ALL TESTS PASSED`**；跳过 0 条。日志：`工作流任务/probe_ui2/run_selftests_ui2b_final.log`（本轮曾先跑一次 206.9 秒同结果，最终树复跑取 246.3 秒）。
2. `python -B -m unittest tests.test_pet_ui` → **599 条、96.17 秒、1 红**：`CloudFitTests.test_the_commands_roll_inside_the_reply_box`（`tests/test_pet_ui.py:6329`，`AssertionError: '#FFFFFF' == '#FFFFFF' : 不再刷云身色`）。根因与第 4013 行同类：上一轮把 `TEntry.fieldbackground` 从字面量 `'white'` 改成 `INPUT_BACKGROUND = COLORS['background_card']`（`#FFFFFF`）后，`cloud.field_bg()` 与 `cloud.fill()` 都成了 `#FFFFFF`；该行用「字符串不相等」表达「不刷云身色」，现在表示法相同就红了。**本轮只被授权改 4013 这一行，未动 6329**；这不是 ReplyBox 清理偶发红，见 F-6 待裁决。其余 598 条绿，未出现 ReplyBoxTests 清理红。
3. `python -B smoke_test.py` → **8/8 通过、0 失败**；`python -B smoke_test.py --affected ui_theme ui_widgets` → **9/9 项通过（含默认 8 项），34 条用例 0 文件红**。
4. 未运行 `--architecture`、未运行 `--all --safe`（按任务书）。

### F-5 截图与目视对比

- `工作流任务/probe_ui2/after2.png`：1280×800，临时空项目根 `probe_ui2/tmp_root/probe_9e1861fz`（`config.json` 的 `downloads_root` 指向空目录，`projects.json` 为空登记）；左侧项目列表为空（「在制作项目 (0)／已完成项目 (0)」），状态栏为「就绪 · 空白探针项目根」，没有真实项目名，也没有「正在打开今日项目…」。
- 对比 `before.png`：左侧 14 个阶段导航、`+ 新建项目`／`打开项目目录`、主区「进入选中的项目 →」等动作按钮恢复为**浅蓝底、无可见描边**的扁平样式，不再有 `after.png` 里的灰色边框和立体边；选中项仍是蓝底白字；按钮文字 10pt、行高实测 33px（32±2）。
- `工作流任务/probe_ui2/after2_focus.png`：把键盘焦点放到未选中的「02 剧本结构」时，出现蓝色键盘焦点环（`COLORS['focus']`），证明扁平化没有把焦点反馈一起删掉。选中项上的焦点环与蓝底同色，属可接受的同色情形。

### F-6 仍需 Claude 裁决

1. **`tests/test_pet_ui.py:6329` 的第 5 条红**：`CloudFitTests.test_the_commands_roll_inside_the_reply_box` 的「不再刷云身色」在 `TEntry` 改成 token 后失效（`field_bg()` 与 `fill()` 都是 `#FFFFFF`，但语义上一是输入框底色、一是云身填充）。已做隔离复现：仅在进程内把 `TEntry` 的 `fieldbackground` 临时改回字面量 `'white'`，该用例立即通过，证明它依赖的是字符串写法而不是两种颜色真的有别。本任务只授权改 4013 一行，故未动。可选处置：①按第 4013 行同样的口径改该断言（但直接比较 `winfo_rgb` 会得到「相等」，需要先确认产品上是否要求小字底色与云身填充必须不同）；②改设计 token 让输入框底色与云身填充真正不同（会改视觉）；③确认该断言随新 token 失效并单独授权一轮。请裁决，勿由本轮擅自扩大范围。
2. **选中项焦点环同色**：`Selected.Nav.TButton` 的焦点边框是 `color.focus`，与选中底色 `color.primary` 同为 `#2563EB`，键盘焦点落在选中项上时环不可见。这是任务书要求「焦点环 `COLORS['focus']`」与「选中项蓝底」共同导致的同色情形；本轮未另造第二焦点色。若要求选中项也有可见焦点环，需要产品再给一个焦点环 token 或允许加外描边。
3. **`TCombobox` 基样式仍 29px**：按任务书第 4 点保持现状，未改；`SelectBox` 仍走 `Tokens.Combobox.TCombobox` 的 33px。

## G 收尾（RUI2c）2026-10-19

### G-1 三问

1. **轮次类型**：修复轮（只改一个测试用例，让它真正验证「小字底色跟输入框、不跟云身」；未改生产代码）。
2. **测试跑了吗？三个基线过了吗？** 跑了任务书点名的两条：`CloudFitTests` 16 条 0 红（2.469s）；`tests.test_pet_ui` 599 条 0 红（85.819s，未出现 ReplyBox 清理偶发红）。未跑 `--architecture`／`--all --safe`／`smoke_test.py`（任务书只点名这两条）。另：直接 `python -B -m unittest tests.test_pet_ui` 在本环境会报 `ModuleNotFoundError: skip_reasons`（`tests/` 不在 `sys.path`），按既有跑法加 `PYTHONPATH=程序\tests` 后即为任务书那条命令，见 G-4。
3. **`project_status.md` 的欠账少了吗？** 没有。按任务书不领号、不改状态页、不提交；本轮只收掉 F-6 第 1 条待裁决项。

### G-2 改动（只此一处）

- 文件：`程序/tests/test_pet_ui.py`。
- 用例：`CloudFitTests.test_the_commands_roll_inside_the_reply_box`（原 6320 行起，现 6320–6340 行）。
- 新增 6322–6331 行：任务书要求的那句注释；`ui_widgets.setup_styles(self.win)` 预热；`ttk.Style` 取 `TEntry.fieldbackground` 原值 → 临时设为 `COLORS['background_primary']` → `addCleanup` 还原。原有顺序不变。
- 改写 6339–6340 行：`assertNotEqual(str(cloud.hint.cget('bg')), cloud.fill())` → `assertNotEqual(self.win.winfo_rgb(hint_bg), self.win.winfo_rgb(cloud.fill()), '不再刷云身色')`。
- 断言 1（`hint.bg == cloud.field_bg()`）及其余断言一字未动；未碰 `wait_for_the_reply`、6 处 `addCleanup`、4013 行；未执行任何 git 写命令；未删文件。

### G-3 实测根因与对任务书字面方案的必要偏差

按任务书字面「`open_chat()` 之前只 `style.configure('TEntry', ...)`」实测**无效**：

- `open_chat()` 首次建回复框（`LineInput`）时会调 `ui_widgets.setup_styles()`；测试进程里 `drama_styles_theme` 尚未置位，于是整表重装输入样式，把 `TEntry.fieldbackground` 写回 `#FFFFFF`。`hint` 在 build／`_render()` 时读到的仍是 `#FFFFFF`，两条断言依旧同色。
- 探针证据（同一 Tk 进程）：override 后 `lookup('TEntry','fieldbackground')` 为 `#F7F8FA` → `pet.cloud()` 后仍 `#F7F8FA` → `open_chat()` 后变回 `#FFFFFF`，`hint.bg` 与 `fill()` 均为 `#FFFFFF`。
- 最小改法（未改生产代码）：同一用例里先 `ui_widgets.setup_styles(self.win)`，把生产启动时 `ui_theme.apply()` 已做过的这件事做掉，再临时改 `TEntry`；此后 `open_chat()` 里的 `setup_styles()` 命中 `drama_styles_theme` 缓存直接返回，临时底色留得住。实测 `hint.bg == '#F7F8FA'`、`fill() == '#FFFFFF'`、两者 `winfo_rgb` 不等。
- 令牌：`COLORS['background_primary']`（`#F7F8FA`）。任务书举例的 `background_muted` 在 `ui_tokens.COLORS` 中不存在，故取实际存在的背景族键；未写 hex 字面量。

### G-4 验证（本轮实测）

环境：`D:\漫剧制作助手\运行环境\Python\python.exe -B`，cwd `程序\`，`PYTHONPATH=程序\tests`。

1. `python -B -m unittest tests.test_pet_ui.CloudFitTests` → `Ran 16 tests in 2.469s`、`OK`、进程退出码 0。
2. `python -B -m unittest tests.test_pet_ui` → `Ran 599 tests in 85.819s`、`OK`、进程退出码 0；未出现 ReplyBox 清理偶发红。

未加 `PYTHONPATH` 时首条命令在 `from skip_reasons import ...` 处报 `ModuleNotFoundError`——不是本轮改动导致，是 `tests/` 未在 `sys.path`（`run_selftests.py` 自己会插入该路径）。

### G-5 仍需 Claude 裁决

1. **预热 `setup_styles()` 这一步**：任务书原方案（只在 `open_chat()` 前改 `TEntry`）实测会被 `open_chat()` 内部的 `setup_styles()` 覆盖而无效；G-3 的预热是任务书允许文件内的最小改法。请确认接受，或另定从 `LineInput` 样式入手。
2. **断言语义还差一层（本轮未动生产代码）**：`cloud.field_bg()` 读的是基样式 `TEntry`，而回复框 `LineInput` 的实际样式是 `Tokens.LineInput.TEntry`。本用例把**基样式**改成 `#F7F8FA` 后，`hint` 跟到了 `#F7F8FA`，但回复框控件实际仍是 `#FFFFFF`。即这条断言证明的是「hint 跟 `field_bg()`／基 `TEntry` 走、且不等于 `fill()`」，尚不等同于「hint 与实际回复框控件同色」。若后者也要成立，需让 `field_bg()` 去读回复框的真实样式（生产改动，超出本轮授权）。

## H 收尾（RUI2d）2026-10-19

### H-1 三问

1. **轮次类型**：修复轮（UI 批次 2 收尾；只改阶段配置面板底栏与说明区的 pack 优先级，未改控件高度／样式，未改测试）。
2. **测试跑了吗？三个基线过了吗？** 跑了任务书点名的 1–3，均 0 红：`tests.test_skills`、定向自检 214 条、受影响冒烟 9/9。**未跑** `--architecture` 与 `--all --safe`（任务书明确禁止）。
3. **`project_status.md` 的欠账少了吗？** 没有。按任务书不领号、不改状态页、不提交；本轮只改源码与本文档。

### H-2 根因（实测）

- `Panel._build()` 原先按「预设行 → 总控 → 厂商／模型 → 阶段专属 → SKILL 区 → 底栏 → 说明区」的顺序 `pack`。Tk 的 `pack` 按调用顺序分配空间：窗口高度不足时，先 pack 的控件先拿满请求高度，后 pack 的底栏拿不到空间而被 `unmapped`（说明区最后 pack，反而因 `expand=True` 吃掉剩余空间）。
- 实测 800×460：面板可用高度 398px；五段固定表单请求高度合计 397px（35＋161＋41＋53＋107），底栏请求 35px。`bottom_bar` 被排到 `y=593`、`winfo_ismapped()==0`，正是 `test_skills.py:1447` 的稳定红。
- 批次 2 把按钮／输入控件抬到 32px 后，固定表单请求高度比旧版多约 34px，使这个原本刚好贴边的小窗口越过临界点；32px 是产品裁决，根因是**空间分配顺序**，不是控件高度。

### H-3 改动（`程序/skill_panel.py`，只此一处）

- 把底栏的创建与 `pack(side='bottom', fill='x', pady=(pad, 0))` 从原 `self.reason` 之后（旧第 320–327 行）前移到 `_build()` 开头、`row` 之前（新第 266–276 行），并加 3 行注释说明优先级：**底栏固定优先 → 不可伸缩的阶段配置 → 可伸缩的技能说明区**。
- `self.state`／`self.preset_hint`／`self.confirm_button` 在底栏内创建的顺序不变，`confirm_button.pack(side='right')` 不变；未改 `skill_panel_support.py`（该文件无底栏／说明区布局代码）、未改 `ui_widgets.py`／`ui_theme.py`／`ui_tokens.py`、未改任何测试、未改 32px／10pt。
- 文件行数 1486（上限 1500），`_build` 72 行（上限 150），`function_size_ratchet`／`module_size_ratchet` 均绿。
- 未执行任何 git 写命令，未删文件，未新增 `.bak_*`。

### H-4 验证（本轮实测）

环境：`D:\漫剧制作助手\运行环境\Python\python.exe -B`，cwd `程序\`，`PYTHONPATH=程序\tests`。

1. `python -B -m unittest tests.test_skills` → **152 条、39.093 秒、`OK`、进程退出码 0**（含 `PanelTests.test_skill_notes_resize_with_the_stage_panel`；修复前该用例在 `test_skills.py:1447` 稳定 `AssertionError: 0 is not true`）。
2. `python -B run_selftests.py -k skill_panel test_skills ui_theme ui_widgets ui_style_engine function_size_ratchet module_size_ratchet test_layers` → **214 条用例、23.8 秒、0 个文件有红、0 条跳过、`ALL TESTS PASSED`**。
3. `python -B smoke_test.py --affected ui_theme ui_widgets desktop skill_panel` → **通过 9 项、失败 0 项**（含定向 `run_selftests` 99 秒、0 个文件有红），`可以进入下一轮`。
4. 未运行 `--architecture`、未运行 `--all --safe`（按任务书）。
5. 修复后实测几何：880×690 说明正文 155px（≥150），880×600 说明区在底栏之上（y 403＋96＝499 ≤ 底栏 y 503），880×900 正文 365px（＞155），800×460 底栏 mapped（y 363、h 35），说明区 `winfo_ismapped()==0`（用例允许）。
6. 说明：stderr 里 Tcl 的 `unknown encoding "cp1252"`／`after script` 输出来自本机 Tk 包索引与既有清理，不是本轮引入；上面的退出码与 `ALL TESTS PASSED` 为准。

### H-5 仍需 Claude 裁决

1. **800×460 的残余挤压**：面板可用高度只有 398px，而「五段固定表单 397px ＋ 底栏 35px」需 432px；底栏优先后，最后 pack 的 SKILL 区在 800×460 被压到 64px（请求 107px），说明区收缩为 0。用例只要求底栏可见、允许说明区不显示，故已通过；若要求 460 高度下 SKILL 勾选区也完整可见，则需要「整页横向不变、纵向可滚动」或放宽 32px 控件高度，均超出本任务授权，请裁决。
2. **是否补响应式收起说明区**：当前说明区在高度不足时由 pack 自然收为 0、window 变高后自动恢复（880×900 实测 manager 仍为 `pack`），未额外加 `<Configure>` 逻辑；若产品希望「先主动收起说明区、再动表单」，可另开一轮加显式响应式，避免引入新魔数阈值。

## 验收与提交（Claude，2026-10-19）

轮次号 1710 由 Claude 在提交时领取（本文件原名 `tasks_round_pending_UI2_result.md`）。含 RUI2b／RUI2c／RUI2d 三次返工。Claude 本机复跑：定向 `-k test_skills skill_panel ui_theme ui_widgets ui_tokens ui_token_contract ui_style_engine design_tokens video_ui ui_edges ui_notifications pet_ui_support test_pet_ui test_layers function_size_ratchet module_size_ratchet` 1005 条 0 红、冒烟 8/8、受影响冒烟 9/9、架构 368/368。三条旧用例由「必须弹系统框」改为断言同一文本落在非模态状态栏且未弹框（产品裁决：可恢复错误默认非模态），其余断言未动。
