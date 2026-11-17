# 任务书 · UI 统一组件标准：共享测宽、图标规范、发送键、Box 框体、控件门禁

> 本任务书自包含，执行者无需本会话上下文。共 8 个独立可回滚的轮次（U0–U7），逐轮按 `程序/AGENTS.md` 规则 27 领号、§2.7 文档先行、§5 验证、§2.6 提交。
> 开工前必读：`程序/AGENTS.md` §0、§2.3、§2.4、§2.7、§5；`程序/ui_components.md`、`程序/design_tokens.md`；`程序/维护记录/UI统一入口路线图_v1.md`。
> **状态接续（2026-11-17 22:03，未完成）**：U0（R3164，16135 字节误认低于门禁 16000 字节，R3178 已压至 16000 并复测）、U2（R3178）、U3（R3195）已在 `dsh-82c63326-f006` 提交，尚未合入 master。当前独立工作树 `dsh-876e046e-e055` 正将其合入 master@d29e1e83：`build_nav_icons.py` 唯一冲突标记已移除并保留两侧逻辑，但 Git 合并未提交；设计与门禁修订仍未复测。R3219 已领号但自动切分支因 merge 失败；无 R3219 结果文件与提交。U4 在来源工作树有六个未提交文件，不能触碰或宣称完成；U1/U5/U6/U7 亦未完成。接手续核对共享轮次和工作树归属、完成 U2/U3 门禁修订与回归、按规则逐轮提交，最终才可合 master；此处不勾选未验证的验收项。
> 与《零依赖边界与媒体预览任务书》同批规划，编号用 U 前缀避免和它的 M 编号冲突，两份的依赖关系见第 6 节。

---

## 1. 总目标

新增功能的 UI 一律使用统一组件和统一标准，不再各写各的。具体要做到：

- 新增下拉卡片、列表、表格按内容测宽统一走共享入口；U1 只迁三处试点，现有其余测宽实现按文件冻结、后续谁改谁迁，不把试点说成全局唯一。
- 图标风格与尺寸统一：输入框图标行保持 MDL2 字形，其余桌面图标以侧栏 Fluent PNG 为准。
- 聊天框、内容框、列表框有统一的外框组件。
- 字体、原生控件、表单控件的取用方式有门禁，新代码不得绕开。

方式是在 `ui_components.md` 写标准、每条标准配一个架构门禁、新代码零容忍、存量冻结只减不增。外观整体不变，不引入任何外部 UI 框架，不新增代码模块。

---

## 2. 已确认决策（不得自行变更）

| # | 决策 | 要点 |
| --- | --- | --- |
| D1 | 目标是一致性与去重 | 不做视觉改版。深色模式、主题切换不在本任务书范围。 |
| D2 | 不引入 GitHub UI 框架 | 已评估 sv-ttk、ttkbootstrap、CustomTkinter（均为 MIT）。项目已有圆角 PNG 按钮、悬停渐变、`ui_tokens`、Fluent 图标，再引入会多出第二个样式权威。可借鉴其"组件清单与命名样式"的思路，不 import、不 vendor。 |
| D3 | UI 物理拆分已完成 | R3100（T10 包化）已把 106 个实体迁入 `ui/`，本任务书不再做拆包。视觉常量统一基本完成（`test_token_boundary` 基线：内联 hex 仅 `previs_monitor.py` 1 处，数字 padding 为 0）。 |
| D4 | 落地方式 | 标准写进 `ui_components.md`（必要时 `design_tokens.md`）；`AGENTS.md` 只加一行指针（它有 16 KB 上限，`test_agent_doc_budget` 守卫）。每条标准同轮配架构门禁（规则 26）。 |
| D5 | 门禁口径 | 新代码零容忍；存量按文件冻结计数，只许减少、不许增加、不许新增文件。基线以门禁自己的 AST 口径实测为准，本任务书里的数字只是估计。 |
| D6 | 存量迁移策略 | 谁改谁迁，不单开大迁移轮。第一批仅试点迁 3 处（见 U1）。 |
| D7 | 不新增代码模块 | 共享代码落点见下表。放不下时**停下来请用户授权**，不自行新建。 |
| D8 | 共享测宽函数 | 放 `ui/ui_popup.py`（现 73 行）。 |
| D9 | 图标尺寸 token | 放 `ui_tokens.py`（465 行）。 |
| D10 | `Box` 框体组件 | 放 `ui_theme.py`（405 行，原有 `Box.TFrame` 样式即定义于此，第 75 行）。**不放 `ui_widgets.py`**：它已达体积上限 1125（`test_module_size_ratchet`）。 |
| D11 | 图标规则（2026-11-17 补充裁决） | 输入框图标行（✦ ＋ 🎤 及其下拉面板行）保持 MDL2 字形 `ICON_FONT`。其他新图标使用 `IconLoader.nav_icon` 加载 Fluent PNG，不新增 emoji；现有阶段文件 PNG 缺失的 14 个 emoji 回退、回收站／清空／素材库三处旧符号，以及视频封面空态，按 AST 口径登记并冻结、只许减少。M3 并未清零 emoji，不改变 REQ-S01-93 的缺图契约。 |
| D12 | 图标尺寸（2026-11-17 补充裁决） | 主导航图标（`render_icons()` 生成，包含 `project_files.png`，以字形表为准）固定 24×24 画布居中；M3 的阶段文件复合图标（`render_stage_file_icons()` 生成的 13 个 `*_files.png`）保持自动裁边，不受主导航尺寸门禁约束。`project_files.png` 是主导航图标，仍须固定 24×24。 |
| D13 | 发送键 | 圆形外框，中间 ↑；运行中中间换 ■。边框色 `border_input_hover`，无填充；悬停边框与图标变 `primary`；不可点用 `disabled_text`；尺寸与 ✦＋🎤 同档。这是对 R3060「发送键主色块 PNG」的有意变更，按 §2.4 同步测试并在结果文件注明。 |
| D14 | 框体分工 | `Card`（圆角 `radius.lg`、`border_default`，21 页在用）保留，用于表单类卡片。`Box`（直角、1px `border_strong`，即剧本页聊天框现用的 `Box.TFrame`）升格为正式组件，用于聊天框、内容框、列表框。两者各有名分，21 页外观不动。 |
| D15 | 第二批门禁范围 | 字体（只取 `FONTS[...]`）、原生控件（浮层与卡片内不新增自配颜色的 `tk.Label`/`tk.Frame`）、表单控件（`Checkbutton`/`Radiobutton`/`Scale`/`Spinbox`/`Notebook` 只用 `ui_theme` 已登记样式名）。 |
| D16 | 不在范围，另行登记 | 键盘焦点覆盖审计、深色模式。面包屑、分页未发现需求。 |
| D17 | 与文件卡片任务的排序 | 已满足：该任务第 8 轮随 R3155 合入 master；U0 的 R3164 文档已纳入卡片、参数滑条和 Lightbox。 |

---

## 3. 现状盘点

### 3.1 已核实

| 事实 | 证据 |
| --- | --- |
| `ui/` 包现有 119 个文件，顶层有大量薄门面 | R3100（提交 `a446bbce`）T10 包化收官。 |
| 17 个 UI 边界门禁已在 | `tests/architecture/`：button、card、combobox、context_menu、copy_entry、data_table、dialog、file_dialog、input、notification、scrollbar_theme、simpledialog、text_component、token、tooltip、ui_icons、busy_state。 |
| 文字测宽没有共享实现 | `ui_widgets._display_width`（全角 2、ASCII 1 的近似）；`ui/asset_batch.py:223–229`、`ui/desktop_files_panel.py:353–373`、`ui/speech_settings_ui.py:48` 各自用 `tkfont.measure`；`ui/storyboard_table_ui.py:53` 有魔法数字 `+14`。完整清单以门禁实测为准（原始 grep 输出被截断，至少 5 处）。 |
| 模型选择器与 `AnchoredPanel` 已按内容撑开 | `ui/stage_model_picker.py:205` 取 `winfo_reqwidth`；`desktop_shared_menus.py:94–99、451–460` 同理。不需要试点。 |
| 浮层有 5 套实现 | `ui/ui_popup.Flyout`（Toplevel）、`desktop_shared_menus.AnchoredPanel` 与 `CandidatePopup`（`place` 浮层，因 Toplevel 画不出 master 边界）、`ui/ui_tooltip.Tooltip`、`ui_widgets.ContextMenu`（`tk.Menu`）。机制不同，不强行合并为一个基类，统一的是测宽、定位钳位（`ui_popup.monitor_bounds`）与卡片样式 token。 |
| 图标有三套体系 | MDL2 字形 `ICON_FONT=("Segoe MDL2 Assets", 11)`（`ui_tokens.py:360`，`ICON_*` 约 54 处引用含测试）；Fluent PNG（`assets/nav/`）；emoji（`ui/desktop_files_panel_filters.py` 的 `STAGE_RAIL_ICONS`，注释写明是占位）。 |
| PNG 实际尺寸不统一 | 读文件头：`continuity` 27×18、`audio` 20×26、`storyboard` 26×22、`project_files` 28×26、`delivery` 26×28 等。原因是 `build_nav_icons.py` 渲染后自动裁边（`TARGET_PX=24` 只是目标）。 |
| 发送键现状 | `desktop_shared_input.py:420–432`：`PrimaryButton`、样式 `Tokens.Composer.Send.TButton`、`assets/nav/send.png`（26×26，主色底）。✦＋🎤 是 `_row_icon` 无底色字形。 |
| 聊天框外框是 `Box.TFrame` | `ui_theme.py:75`：`background=BG, bordercolor=border_strong, relief='solid', borderwidth=1`；全仓只有 `ui/desktop_writing_page.py:242` 一处使用。`ui_components.md` 与 `design_tokens.md` 均无聊天框条目。 |
| `Card` 的实现 | `ui_widgets.py:149–165、834–839`：圆角底图、`Tokens.Card.TFrame`、默认 padding `lg`。 |
| 体积上限 | `tests/architecture/test_module_size_ratchet.py`：新模块上限 1000 行；`ui_widgets.py` 登记 1125（实际 1125，不能再增）。`ui_theme.py` 405 行、`ui_tokens.py` 465 行、`ui/ui_popup.py` 73 行均有余量。 |
| `tk.Toplevel` 生产命中只有两处 | `ui/ui_splash.py:20`、`ui/ui_tooltip.py:159`，均为无边框提示层，`ui_components.md` 第 149 行明确它们不属于对话框，所以未被 `test_dialog_boundary` 拦截是正常的。`messagebox` 的生产命中只是 `ui_widgets.py` 的文档字符串。 |
| 原生与表单控件使用量（本任务书作者自行统计，108 个 tkinter 文件） | `tk.Label` 44 处/17 文件、`tk.Frame` 30 处/11 文件（集中在 `desktop_shared_menus.py` 14、`ui/stage_model_picker.py` 13）、`tk.Canvas` 15 处；`Checkbutton` 16、`Radiobutton` 3、`Scale` 1、`Spinbox` 4、`Notebook` 1（共 25）、`Listbox` 3；内联字体元组 10 处/6 文件。统计用正则，门禁用 AST，两者数字可能不同。 |
| `ui_widgets.py` 没有表单控件封装类 | 只有 `TCheckbutton`、`TSpinbox` 的全局样式；`ui_theme.py` 配了 `TNotebook.Tab`、`TCheckbutton` 的布局。 |

### 3.2 执行者在对应轮次开头先核实

1. **`ICON_SEND`（`\uE74A`）与 `ICON_STOP`（`\uE71A`）在 Segoe MDL2 Assets 里的字形**：是否正好是向上箭头与方块。作者印象如此但未目视确认（U4）。若不是，改用 `ui_tokens` 新增一对专用常量，不要硬凑。
2. **圆形外框的实现位置**：`ui_widgets.py` 已满，圆形底图不得加在它里面。先读 `ui_rounded.py` 与 `ui/ui_composer_style.py`（后者承载输入框图标按钮样式，并由 `ui_widgets.setup_styles` 注入）的现有能力，优先在 `ui/ui_composer_style.py` 内扩展（U4）。
3. **`ui_theme.py` 能否放下 `Box`**：405 行有余量，但需确认 `test_complexity_ratchet`、`test_function_size_ratchet` 对函数大小与参数个数的登记值（U5）。
4. **`HITL` 第 8 轮合并后新增了哪些组件与 token**：逐个对照本任务书的门禁口径，必要时把它们纳入 U0 的标准文档，或把违规项登记为存量冻结（U0）。
5. **`desktop_shared_menus.py` 里 14 处 `tk.Label`/`tk.Frame` 是否都是浮层内部结构**：决定 U6 的存量冻结口径与是否需要给浮层卡片提供一个命名样式（U6）。

---

## 4. 分轮拆解

每轮独立可回滚，先改文档再改代码（§2.7）。每轮声明类型，收尾按 §7 出结果文件。所有门禁的存量基线以该门禁自己的 AST 口径当轮实测，写入测试文件头注释并注明口径。

### U0 文档轮：标准先行

**状态**：R3164 已在功能分支提交；R3164 结果将 16135 字节误认作低于门禁 16000 字节，R3178 把 `AGENTS.md` 压至 16000 字节并复测 5/5。其余勾选以实际合并树复核，不能把原报告当作当前验收。**类型**：文档轮，不跑 smoke 与 selftest。**前置**：D17 已满足。

改动：
- `ui_components.md` 新增章节：浮层与测宽、图标（含 MDL2/PNG 边界）、框体（`Box` 与 `Card` 的分工）、发送键、字体、原生控件、表单控件。每节写明"用哪个入口、禁止什么、门禁名"。
- `design_tokens.md` 补图标尺寸 token 与 `Box` 的边框、内边距取值。
- 把文件卡片任务新增的组件与 token 并入同一套标准，登记它们已有的违规项为存量。
- `AGENTS.md` §2.5 规则 34 旁加一行指针指向新章节，不展开；改后确认 `test_agent_doc_budget` 不超 16 KB。
- 在 `docs/stages/` 相关文档补 REQ/DES 编号，供后续测试锚定。

验收：
- [ ] `ui_components.md` 每一节都写明入口、禁止项、对应门禁名，且门禁名与 U1–U6 的实际测试文件名一致。
- [ ] 文件卡片任务新增的组件已纳入标准，其违规项有登记。
- [ ] `AGENTS.md` 仍在 16 KB 预算内，新增内容不超过一行指针。
- [ ] REQ/DES 编号可被后续测试锚定。

### U1 共享测宽函数与三处试点

**状态**：未提交／未验收；`responsive_ui` 与 `ui_widgets` 等现有直接测宽保留并登记冻结，试点不代表全仓唯一实现。**类型**：功能轮。

改动：
- 在 `ui/ui_popup.py` 新增共享测宽函数：输入字体（取自 `FONTS`/token）与文本集合，返回像素宽度；含上限钳位参数。真实字体测宽，不再用字符数近似。
- 试点迁 3 处：
  1. `ui_widgets.SelectBox` 的 `_display_width` 与 `_fit_width` 改调共享函数（注意 `ui_widgets.py` 不能变长，迁移应净减行数）。
  2. `ui/desktop_files_panel.py` 的 `_fit_script_width`（第 353–373 行）。
  3. `ui/storyboard_table_ui.py` 第 53 行附近，去掉魔法数字 `+14`，改取 `SPACING` token。
- 新增门禁 `test_text_measure_boundary.py`：新代码不得直接调用 `font.measure` 或手写字符宽度近似，必须经共享函数；存量按文件冻结。

验收：
- [ ] 共享函数有单测：全角、ASCII、混合、空字符串、超过上限四类输入。
- [ ] `SelectBox` 在含中文长选项时宽度能完整显示选项且不超过 `COMBOBOX_MAX_WIDTH`；用真 Tk 量几何。
- [ ] 文件面板与分镜表列宽行为不变（既有 `test_files_panel*`、分镜表相关测试全绿）。
- [ ] 新门禁通过，且对"新增一处直接调用 `measure`"的坏样本能报错。
- [ ] `ui_widgets.py` 行数不高于 1125，`test_module_size_ratchet` 通过。
- [ ] 默认冒烟 8/8；`run_selftests.py -k select_box files_panel storyboard_table ui_widgets` 全绿。

### U2 图标固定画布与尺寸门禁

**状态**：R3178 已在功能分支提交，原门禁扫描全部 PNG、与后合入的 M3 图标冲突；合并树需按 D12 裁决修正门禁并复测。**类型**：功能轮。

改动：
- `scripts/build_nav_icons.py` 的 `render_icons()`：主导航图标居中放入固定 24×24 画布，尺寸从 `ui_tokens` 图标尺寸 token 取值；M3 `render_stage_file_icons()` 保留其自动裁边。
- 主导航 PNG 重生入库；M3 的 13 个 `*_files.png` 不随本轮重生。
- 侧栏、图标列、`project_files` 入口钮的 padding 若依赖图标宽高撑开，逐处核对。
- `test_nav_icon_size_boundary.py` 按 `build_nav_icons.ICONS` 的主导航字形表逐个查 PNG 文件头宽高等于 token，并核对文件存在；只豁免 M3 的 13 个阶段文件复合图标，不豁免任何主导航图标，坏尺寸样本仍应报错。

验收：
- [ ] 所有主导航 PNG 为 24×24、M3 阶段文件图标豁免，合并树门禁通过。
- [ ] 侧栏 13 个阶段图标与设置、项目分组图标对齐，在 100% 与 125% 缩放下肉眼复核，截图存入结果文件。
- [ ] `test_ui_icons`、`test_login_gate`、`test_page_lock` 等既有图标测试全绿。
- [ ] 缺失 PNG 时的退回行为不变。

### U3 图标取用入口门禁

**状态**：R3195 已在功能分支提交；M3 的缺图 emoji 回退和随后新增的三个旧符号尚需按 D11 补齐冻结门禁与合并树回归。**类型**：功能轮。

改动：
- 新增门禁 `test_icon_source_boundary.py`：
  - 新代码取图标只能走 `IconLoader.nav_icon`。
  - `ICON_FONT` 字形只允许出现在输入框图标行及其下拉面板：`desktop_shared_input.py`、`desktop_shared_menus.py`、`ui/ui_composer_style.py`，以及已使用 `Tokens.Composer.Icon.TButton` 样式的位置（`ui/workflow_settings_dialog.py` 的麦克风钮）。允许清单写进测试，只减不增。
  - 新代码不得再用 emoji 当图标；M3 的 `STAGE_RAIL_ICONS` 13 项＋「全部」1 项作为 PNG 缺失回退保留，回收站／清空／素材库三个旧符号与视频封面空态也登记为受控存量，冻结方式须实际识别这些 AST 形态。
- 在 `ui_tokens.py` 为 MDL2 图标登记尺寸注释，不增删常量。

验收：
- [ ] 门禁通过；"新增 `from ui_tokens import ICON_FOLDER` 并用于非允许文件"的坏样本能报错。
- [ ] emoji 存量被准确冻结，不误伤文案里的普通符号（先实测判定口径，写入结果文件）。
- [ ] 既有引用 `ICON_*` 的测试全绿。

### U4 发送键改圆形外框 + ↑

**类型**：功能轮。**核实**：见 3.2 第 1、2 项。

改动：
- 按 D13 实现圆形外框发送键，样式放 `ui/ui_composer_style.py`。移除发送键对 `assets/nav/send.png`、`stop.png` 的使用；若这两张 PNG 再无引用，从 `build_nav_icons.py` 字形表与 `assets/nav/` 一并删除（删除前全仓 grep 确认零引用）。
- 运行中↔空闲的状态切换入口保持为 `desktop_script_pages.update_script_interrupt_button()`（见 `docs/stages/S01_剧本准备.md` DES-S01-62），只换外观。
- 同步 REQ/DES 文字：DES-S01-62 里"发送键主色底＋Fluent PNG"的描述改为新样式。
- 同步测试契约（§2.4）：`tests/test_script_composer.py`、`tests/test_shared_input_ui.py` 对发送键样式与图像的断言按新契约改写，行为类断言（点击触发发送、运行中变终止）保持原样。结果文件注明契约变化。

验收：
- [ ] 发送键为圆形外框、中间 ↑；运行中为 ■；悬停、不可点、聚焦三态都有可见变化，截图存入结果文件。
- [ ] 与 ✦＋🎤 同一档尺寸，在输入框图标行里垂直居中、间距一致（真 Tk 量几何）。
- [ ] 点击发送、Enter 发送、运行中点终止、Esc 终止的行为不变。
- [ ] 输入框其余图标的外观未变。
- [ ] `test_script_composer`、`test_shared_input_ui`、`test_idea_chat` 全绿；结果文件逐条列出被改写的断言及原因。

### U5 Box 框体组件与聊天框迁移

**类型**：功能轮。

改动：
- 在 `ui_theme.py` 把现有 `Box.TFrame` 升格：样式名、边框色、内边距取 `ui_tokens` 的 token（`border_strong`、`SPACING`），并提供一个创建入口函数；`ui_components.md` 有对应条目（U0 已写）。
- `ui/desktop_writing_page.py:242` 的 `ttk.Frame(style='Box.TFrame', ...)` 改走新入口，外观保持不变（像素级对比截图）。
- 新增门禁 `test_box_boundary.py`：聊天框、内容框、列表框新代码必须用 `Box` 入口，不得直接写 `style='Box.TFrame'` 或自拼 1px 边框；存量仅 `desktop_writing_page.py` 一处，迁移后清零。
- 若放进 `ui_theme.py` 触碰复杂度或函数大小棘轮且无法精简：**停下来请用户授权**，不自行新建模块。

验收：
- [ ] 剧本页聊天框迁移前后截图一致。
- [ ] 全仓除 `ui_theme.py` 外不再出现 `Box.TFrame` 字面量；门禁通过且坏样本能报错。
- [ ] `Card` 的外观与 `test_card_boundary` 不受影响。
- [ ] `test_module_size_ratchet`、`test_complexity_ratchet`、`test_function_size_ratchet` 通过。

### U6 字体、原生控件、表单控件门禁

**类型**：功能轮（以门禁为主）。**核实**：见 3.2 第 5 项。

改动：
- 新增三个门禁，扩展 `test_token_boundary` 的口径或各自成文件（沿用其按文件冻结的写法）：
  1. **字体**：新代码不得写内联字体元组，只取 `FONTS[...]`；存量冻结（作者统计约 10 处/6 文件，以 AST 实测为准）。
  2. **原生控件**：浮层与卡片内新代码不得新增自配颜色的 `tk.Label`/`tk.Frame`；存量冻结（约 44 + 30 处，集中在 `desktop_shared_menus.py` 与 `ui/stage_model_picker.py`）。
  3. **表单控件**：`Checkbutton`/`Radiobutton`/`Scale`/`Spinbox`/`Notebook` 新代码只能用 `ui_theme` 已登记的样式名，不得内联配置外观；存量冻结（作者统计 25 处/11 文件，另 `Listbox` 3 处单独记录）。
- 不为存量做批量迁移（D6）。

验收：
- [ ] 三个门禁各有"新增违规"的坏样本，均能报错。
- [ ] 三个门禁在当前树上全绿，基线值与文件清单写入测试文件头并注明 AST 口径。
- [ ] 与作者统计数字不一致时，结果文件说明原因，不为凑数调整口径。

### U7 收尾

**类型**：文档轮。

- 按规则 35 输出 `程序/tasks_round/任务完成/UI统一组件标准任务书·任务完成.md`：逐条列 U0–U6 每个验收勾选的证据（轮次号、结果文件、commit hash）；未完成项给处置并附用户确认凭据。
- `ui_components.md` 的门禁名与最终测试文件名核对一遍。
- 登记遗留项：键盘焦点覆盖审计（`takefocus` 11 处、含 focus 的行 188 处，数字不足以判断覆盖是否完整）、深色模式，以及各门禁的存量冻结清单，写入 `维护记录/优化待办队列.md` 并附指针。

验收：
- [ ] 完成文件覆盖本任务书每一条验收勾选，证据或处置标记数不少于任务条数。
- [ ] 遗留项已登记到待办队列。

---

## 5. 测试方案

- 每轮：`python smoke_test.py`（U0、U7 为文档轮，不跑）。
- 改活跃逻辑：`python smoke_test.py --affected <模块名>`；被多处引用的模块（`ui_widgets`、`ui_tokens`、`ui_theme`）覆盖全部消费者。
- 含 Tk 的测试由运行器强制在隐藏桌面运行，新测试放 `程序/tests/`，架构门禁放 `程序/tests/architecture/`。
- 每新增一个架构门禁，同轮更新 `architecture.md` 的"当前架构门禁清单"、基线数量与结果报告。
- 门禁必须带坏样本自审（参照 `test_gate_selfaudit.py`），证明违规会被拦下。
- 涉及 `ui_widgets`、`ui_theme`、Tk 生命周期的轮次，合入 master 前触发一次全量（§5）。
- 本任务书不新增 AGENTS §2.3 硬约束：标准写在 `ui_components.md`，每条有测试，AGENTS 只留指针。

---

## 6. 与其他任务的关系

| 任务 | 关系 | 处置 |
| --- | --- | --- |
| 《文件卡片与HITL交互任务书》 | 同样改 `ui_components.md`，新增卡片、参数滑条、Lightbox | R3155 已合入 master，U0 前置已满足；其新增组件纳入标准审查。 |
| 《零依赖边界与媒体预览任务书》M3（R3191，阶段图标换 PNG） | 新增 `assets/nav/<stage>_files.png`、保留缺图 emoji 回退 | M3 已合入主干；经 2026-11-17 用户裁决，U2 只固定主导航图标，13 个阶段文件复合图标维持自动裁边；U3 冻结 14 个缺图回退，而非宣称 emoji 清零。 |
| 《零依赖边界与媒体预览任务书》M4、M5（封面与缩略图列） | 与文件卡片第 8 轮的"视频音频卡"有重叠 | 分工：M4 只做 ffmpeg 生成封面与波形并缓存（数据层）；卡片外观归文件卡片任务；项目文件面板缩略图列归 M5。文件卡片第 8 轮合并后，需删除 M4、M5 中与其重复的部分。 |
| R3060 桌面界面打磨 | U4 有意变更其"发送键主色块 PNG" | 在 U4 的结果文件注明契约变化与回归证据。 |

---

## 7. 风险与回滚

| 风险 | 处置 |
| --- | --- |
| 固定 24×24 画布导致侧栏图标视觉位置偏移 1–2 px | U2 验收含 100% 与 125% 缩放的肉眼复核截图；偏移超过容忍时调整图标按钮 padding，而不是回退画布。 |
| 重跑 `build_nav_icons.py` 的 Pillow 版本或字体差异使图标整体变样 | 脚本只在开发机跑；提交前对比新旧 PNG 缩略图，差异明显时保留旧资产并记入欠账。 |
| `Box` 放进 `ui_theme.py` 触碰复杂度或函数大小棘轮 | 先精简；仍不行就停下请用户授权，不自行新建模块（D7）。 |
| 圆形外框在 125%/150% 缩放下边缘锯齿 | 底图按 `tk scaling` 系数生成（`ui_widgets._install_card_style` 已有同样做法），U4 验收在两档缩放下截图。 |
| 门禁存量基线与作者估计不符 | 以门禁自己的 AST 口径当轮实测为准；差异在结果文件说明，不修改口径凑数。 |
| 文件卡片任务第 8 轮的前置依赖 | R3155 已合入，U0 的前置阻塞解除；不得再按旧风险条款停工。 |
| M3 与 U2 同改 `assets/nav/` 与 `build_nav_icons.py` | 已合入的 M3 保留复合图标自动裁边；U2 只固定主导航图标，门禁以字形表区别两类，合并树实测而不是按历史结果追认。 |

回滚：每轮是一个可独立回滚的变更集，回滚用 `git revert`。U2 的 PNG 批量重生成随该轮提交，回滚即恢复旧资产。门禁随各自轮次提交，回滚时一并撤回。

---

## 8. 交付留痕

- 每轮：`程序/tasks_round/tasks_round_N_result.md`，开头回答三问（类型、测试与基线、欠账变化）。
- 任务书维度：U7 输出《任务完成文件》，并确认 `任务完成/README.md` 存在。
- 提交：`scripts\dev.py commit -m "R<N>: 说明"`，改 `.py` 须带 `--tests`。
- 不 `git push`，除非用户明确要求。
- 本任务书的验收勾选必须在完成文件中逐条出现（规则 35，`test_taskbook_closure` 守卫）。
