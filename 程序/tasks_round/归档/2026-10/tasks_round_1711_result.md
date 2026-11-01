# R1711：结构治理轮·执行（UI 批次 4）——项目选择与恢复窗：小窗口下动作区不裁字

## §7 三问

1. **本轮属于 §3 哪种类型？** 结构治理轮（UI 批次 4，页面级收口），范围严格限于 `desktop_project_pages.py` 与其新增测试。按 `RUI_common.md` 不认领轮次、不改 `project_status.md`、不执行任何 git 写命令；验收与提交由 Claude 完成。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8 绿**；`--affected desktop_project_pages` **9/9 绿**；任务书定向命令命中 127 条（172.2 秒），其中 `test_ui_batch4_desktop_project_pages` 3/3、`test_layers` 5/5，仍有 3 条红全部来自别的批次正在改的 `desktop.py`／`test_ui_edges`（详见 C 节），不是本文件引入。**架构门禁基线**按 `RUI_common.md` 不跑全量 `--architecture`（只主动跑了 5 个相关模块，52/53 绿，1 条红由他批 `desktop.py.__init__` 改动触发）；**全量基线** `--all --safe` 同样按该文件不跑，均留给 Claude。
3. **project_status.md 的欠账少了吗？** 未改 `project_status.md`，欠账数字不变；本批源码改动按项目规则计一次源码轮，由 Claude 在验收入口统一记账。

## A 现状核对（改前）

- **项目选择窗底栏**：`_choose_project_impl` 原第 310–315 行把 5 个按钮塞进同一个 `ttk.Frame` 单行 `pack`；评审报告实测 640×480 下内容宽 596、底栏请求 628，“进入项目 →”被压到 86px（请求 118px）。源码中确有 5 个按钮同排、无换行兜底。
- **项目首页动作区**：`project_home` 原第 318–334 行把 8 个按钮逐个 `self.button(self.content, ...)` 竖排 `pack`，最后一个“重建项目索引”在 1280×800 下只露一半（`工作流任务\probe_ui2\after2.png` 已记录）。
- **标题字号**：原第 223 行 `font=('Microsoft YaHei UI',17,'bold')`，不在 `FONTS` 四档层级内。
- **数字 padding / hex**：`tests/architecture/test_token_boundary.py` 登记本文件数字 `padx/pady` 7 处（22、18、8、12、6、3 等标量），内联 hex 0 处。
- **恢复类弹窗**：`重新查找项目` 的候选目录窗是 `chrome=False` 手工排布，只有一颗“认领此目录”按钮、没有取消；回收站恢复窗的“刷新”夹在“关闭”与两个主操作之间，动作层级不统一。
- **可复用入口**：`responsive_ui.FlowBar` 已是全仓在用的“可换行动作栏”，直接复用，未新建第二套换行组件、未改 Canvas 自绘。

## B 改动（只改允许的文件）

**`程序\desktop_project_pages.py`**

- 新增 `_project_action()`（第 57 行）：项目动作统一进 `FlowBar`，主操作改 `Tokens.Primary.TButton`；仍复用 `self.button()`，宠物点击接缝与 `self.safe()` 语义不变。
- 项目选择窗（`_choose_project_impl`，第 228–332 行）：
  - 动作区改为 `FlowBar` 并**先 pack 到底边**（第 231–232 行），矮窗口只压缩项目列表，不把按钮挤出可视区；窄窗由 `FlowBar` 自动换行，每个按钮保持请求宽度。
  - 页标题改 `FONTS['heading_1']`（16pt bold，第 233 行）；标题／说明／列表的 22px、18px、12px 等全部换成 `SPACING['xl']/['md']/['sm']`。
  - 警告提示的固定 `wraplength=590` 改为 `TEXT_DESC['wraplength']` 起步，并在 `<Configure>` 中按窗口宽度减两侧留白动态折行（第 237–242 行），500px 宽不再把窗口顶宽。
  - 按钮顺序改为“进入项目 →”（唯一 primary，第一位）→ “+ 新建项目”→“恢复回收站内容…”→“重新查找项目”→“删除选中项目”；主操作在 500/640 两档都留在第一行、完整可点。“+ 新建项目”由 primary 降为 secondary，保证一屏只有一个主操作。
  - “重新查找项目”候选窗（第 299–312 行）从 `chrome=False` 改为标准 `BaseDialog` chrome：内容进 `picker.content`，底部用 `add_action('取消')`＋`add_action('认领此目录', primary=True)` 统一动作区；认领成功后用 `picker.close()` 走统一关闭语义。
- 项目首页（`project_home`，第 333–349 行）：`FlowBar` 先占底边（第 337 行），树列表填剩余空间；8 个动作改走 `_project_action()`，“进入选中的项目 →”使用主按钮样式并排在第一行第一位，任何一档都不裁字。
- 回收站恢复窗（`open_recycle_recovery`，第 390–441 行）：说明文字的数字 padding 换成 `SPACING['xs']/['sm']`；动作顺序重排为“关闭”最右、“恢复选中条目”“恢复整批”紧挨其左、“刷新”最左的次操作（第 437–440 行），主次层级与“取消在旁”统一。
- 本文件已无内联 hex、无数字 `padx/pady`（`test_token_boundary` 基线只降不升）。`ui_tokens.py`、`ui_widgets.py`、`ui_theme.py`、`design_tokens.md`、`ui_components.md` 一律未改。

**`程序\tests\test_ui_batch4_desktop_project_pages.py`（新增，docstring 含「UI 批次 4」）**

- 真 Tk 根窗口，640×480、500×380、1280×800 三档分别渲染项目首页（`ProjectPagesMixin.project_home`）与项目选择窗（`ProjectPagesMixin._choose_project_impl`）。
- 每个动作按钮断言：`winfo_ismapped()`、`winfo_width() >= winfo_reqwidth()`、上下边都不越出窗口；主操作另断言 `style == Tokens.Primary.TButton`。
- 项目根用 `tempfile.TemporaryDirectory()` 下两个空项目目录，不打开、不读取任何真实项目。
- 另加一条源码令牌检查：禁止 17pt 手写标题、禁止数字 `padx/pady`。
- 文件名包含 `desktop_project_pages`，因此 `smoke_test.py --affected desktop_project_pages` 能命中该测试（否则定向门禁报“未命中任何测试”）。

## C 验证与截图

**最终实测（本轮真实运行，非历史凭据）**

| 命令 | 实际结果 |
| --- | --- |
| `python -B -m unittest tests.test_ui_batch4_desktop_project_pages -v` | 3/3 OK（最终 2.1 秒；多轮复跑均绿） |
| `python -B -m unittest tests.test_project_recovery tests.test_project_rename_reconcile -v` | 22/22 OK（桌面项目源码探针、首页树刷新等既有用例） |
| `python -B smoke_test.py` | 8/8 通过 |
| `python -B smoke_test.py --affected desktop_project_pages` | 9/9 通过，定向门禁 0 个文件有红（21 秒） |
| `python -B run_selftests.py -k desktop_project ui_edges project_picker test_layers function_size_ratchet module_size_ratchet test_ui_batch4` | 127 条 / 172.2 秒，3 条红；本批相关项全绿：`test_ui_batch4_desktop_project_pages` 3/3、`architecture.test_layers` 5/5、`architecture.test_module_size_ratchet` 2/2 |
| `python -B run_selftests.py -k test_ui_batch4` | 3 条 / 2.0 秒，0 个文件有红 |
| `python -B run_selftests.py -k desktop_startup_perf` | 14 条 / 19.3 秒，0 个文件有红（含真实首日项目选择框、grab 与首帧几何） |
| `python -B -m unittest tests.architecture.test_token_boundary tests.architecture.test_data_table_boundary tests.architecture.test_button_boundary tests.architecture.test_project_entry_boundary tests.architecture.test_startup_budget` | 53 条 / 18.1 秒，52 绿 1 红；红的是 `test_data_table_boundary::test_project_selection_pages_use_data_table_not_a_page_treeview`（详见下） |

**定向命令的 3 条红（均非本文件）**

1. `architecture.test_function_size_ratchet::test_registry_tracks_real_sizes`：`desktop.py::__init__` 实际 132 行，登记表仍留 175 行上限，报“已不超限，请从登记表删除”。`desktop.py` 当前是他批未提交改动（`git status` 可见），不在本批允许范围。
2. `test_ui_edges::test_table_hover_clears_when_wheel_scrolls`：`table.yview()[0]` 为 0，测试的是**首帧管理页**的表格滚动，不经过本文件。
3. `test_ui_edges::test_restored_main_window_recomputes_page_scroll_before_wheel`：`d.canvas.yview()[0]` 为 0，测试的是**分镜定稿页**画布滚动，同样不经过本文件。

**额外相关架构自查（不在任务书验收清单，主动跑）**

`test_token_boundary`、`test_button_boundary`、`test_project_entry_boundary`、`test_startup_budget` 均通过；`test_data_table_boundary` 的首条用例通过（全仓裸 Treeview 仍只有 `desktop.py:1`＋本文件 `:2`），但 `test_project_selection_pages_use_data_table_not_a_page_treeview` 报 `1 != 2`：他批已把 `desktop.py.__init__` 里的 `ttk.Treeview` 移出（AST 现为 `__init__:0`、`project_home:1`），而门禁仍冻结“`__init__`＋`project_home` 合计 2”。本文件 `project_home` 的 1 处 Treeview 原样保留；需 Claude 在合并他批改动时同步该门禁的口径（不是本批允许修改的测试）。

对照证据：同一命令在本轮改动后、他批继续改 `desktop.py`／`keyframe_comfy.py`／`skill_panel.py` **之前**的首跑为 127 条、149.9 秒、仅 `module_size_ratchet` 1 条红；首跑后他批把 `skill_panel.py` 从 1653 行拆到 1494 行，`module_size_ratchet` 随即转绿，同时 `desktop.py` 被改到 `__init__` 132 行并出现上述两条滚动红。这些红随他批文件变化而出现，本批未触碰这些文件，也未回退他批改动。另：该定向命令跑完后，本批只在新增测试里补强了“顶边不越界”“主按钮样式”“无 modal=True”三组断言并单独复跑 3/3；生产文件在该命令之后未再改动。

**截图（`工作流任务\probe_ui4\`，空临时项目根 + 两个空项目目录）**

- 选择窗：`dialog_640x480.png`、`dialog_500x380.png`、`dialog_1280x800.png`
- 首页：`home_640x480.png`、`home_500x380.png`、`home_1280x800.png`
- 探针与原始日志：`show_project_ui.py`、`capture.ps1`、`probe_*.out`、`rect_*.json`、`run_selftests_ui4*.log`、`smoke_ui4*.log`、`new_test_final.log`
- 500×380 实测（`probe_home_500x380.out` / `probe_dialog_500x380.out`）：首页 8 个按钮宽＝请求宽（138/112/173/186/132/108/106/93），`mapped=1`；选择窗 5 个按钮宽＝请求宽（118/118/132/118/118），`mapped=1`。三档截图均为按钮文字完整、主操作可见。

**未运行（按 `RUI_common.md` §验证）**：`smoke_test.py --architecture`、`run_selftests.py --all --safe`；未启动真实应用、未读取/打开任何用户项目。

## D 断言未动与需裁决事项

- **断言未动**：未修改任何既有测试的断言、未加 skip、未改期望值；只新增 `tests/test_ui_batch4_desktop_project_pages.py`。
- **需 Claude 裁决 1（有意的主次调整）**：选择窗“+ 新建项目”由 `PrimaryButton` 降为 `SecondaryButton`，让“进入项目 →”成为唯一主操作；若产品要求“新建”也保持实心主色，请回退这一处样式。
- **需 Claude 裁决 2（换行后的顺序）**：“进入项目 →”放在 `FlowBar` 第一位。640/500 两档它稳定留在第一行、不会因为换行被甩到第二行末尾；若必须保持“主操作靠右”的传统对话框顺序，需要 `FlowBar` 支持右对齐，而 `responsive_ui.py` 不在本批允许范围。
- **需 Claude 裁决 3（恢复窗顺序）**：回收站恢复窗现在“关闭”最右、两个“恢复”紧挨其左、“刷新”最左。`BaseDialog.add_action` 的 `side='right'` 语义决定了先加的最右，改成绝对右对齐需要改 `ui_widgets.py`（本批禁止）。
- **需 Claude 裁决 4（架构门禁口径）**：`tests/architecture/test_data_table_boundary.py::test_project_selection_pages_use_data_table_not_a_page_treeview` 期望 `__init__`＋`project_home` 合计 2 处 Treeview，但 `desktop.py.__init__` 已被他批移出该控件，当前实测 1。这属于他批结构改动的配套门禁登记，本批不得改 `desktop.py` 或该测试；请在合并时同步期望或确认他批的替代入口。
- **契约变化**：候选目录窗由无 chrome 浮窗改为标准 `BaseDialog`（有标题栏/内容区/统一动作区），这是任务书第 3 条的“统一动作区”要求；未改其业务逻辑。
- **建议新增令牌**：本批页面未新增魔法值，无必须新增令牌。可选建议：`responsive_ui.FlowBar` 内部仍写死行内间距 5px、行间距 4px（不在本批允许文件内），后续可收敛为 `SPACING['xs']` 或其派生令牌，由 Claude 统一决定。
- **未覆盖**：真实 125%/150% DPI、真实主窗口 800×600 下的整页滚动、恢复窗的真实回收批次操作；本批只量动作区几何与构建路径。

## E 提交状态

未提交。由 Claude 验收后提交。

## 验收与提交（Claude，2026-10-19）

轮次号 1711 由 Claude 提交时领取（原名 `tasks_round_pending_UI4_result.md`）。补交 RUI4b：两处 `skipTest(PLATFORM_TKINTER)` 登记进 `维护记录/skip台账.json`。Claude 在隔离验证工作树（已提交版本＋本批文件）复跑：定向 163 条 0 红、冒烟 8/8、架构门禁除工作树环境项外全绿，skip／函数行数／数据表边界等 37 条复查 OK。D 节 1–3 项（新建项目降为次按钮、「进入项目」置首、恢复窗关闭最右）验收接受。
