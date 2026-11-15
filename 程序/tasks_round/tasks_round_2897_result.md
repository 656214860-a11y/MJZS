# R2897 功能轮结果：左侧导航图标轨改版——阶段「编号+实心图标」、项目区图标化与选择器
<!-- round-evidence: {"commit_base": "e231a3b7", "credential_hits": 0, "evidence_sha256": "5afe4c690c7ba2b6", "exit": 0, "failed": 0, "passed": 140, "round": 2897, "tests": "run_selftests.py -k ui_icons compact_layout startup_perf page_lock account_entry account_page login_gate ui_batch3 rename_reconcile switch_guard sidebar_project_title resize_coalescing button_consistency page_cache paint_freeze claude_writing_session"} -->

- 轮次类型：§3.1 功能轮。
- 需求：左侧文字目录全部改图标（参考 X 桌面：浅灰胶囊+深色图标）；侧栏收窄到「数字+图标」；右侧功能区获得更多横向空间；图标简单易懂、一眼识别工作阶段；数字保留；「＋新建项目」「打开项目目录」与「在制作/已完成」分组改图标并入项目列表区；项目名改选择器不占空间；全应用图标风格统一、实心。

## 改动

- **图标资产管线（运行时零第三方依赖）**：图标字形取自 Microsoft Fluent System Icons（Filled 实心版，MIT），字体与许可证入库 `assets/fonts/`；`scripts/build_nav_icons.py`（开发期，需 Pillow，不进运行环境）按 2 倍率渲染裁边生成 20 枚 PNG 到 `assets/nav/`；运行时 `ui_icons.IconLoader.nav_icon()` 按「Tk 宿主+文件路径」缓存加载，资源缺失返回 None，页面不写死文件名。
- **语义映射唯一入口** `desktop_page_registry.py`：`NAV_STAGE_ICONS`/`PAGE_NAV_ICONS`（13 阶段+参考网站+会员账户）、`ASSET_ROSTER_ICON`、`PROJECT_GROUP_ICONS`、`PROJECT_ACTION_ICONS`、`nav_label()`（'00'…'14' 短编号）。
- `desktop.py` 侧栏：阶段钮＝`nav_label` 编号＋图标 `compound='left'`，`Tooltip` 给全称；项目区改为「分组筛选图标×2＋`SelectBox` 项目选择器＋新建/打开目录图标×2」，全部 `RailIcon.TButton`＋Tooltip；移除侧栏项目 Treeview（`self.list` 及 `<<TreeviewSelect>>`/`<<TreeviewOpen>>` 契约随之移除）。
- `desktop_project_pages.py`：新增 `_sync_project_picker(snap=)`（Path 归一化比较、分组值防御、`●` 标当前项）、`set_project_group`、`_sync_project_group_styles`、`project_picker_menu`（右键菜单与项目列表行一致）；`mark_current_project`/`restore_project_selection`/`set_project_status`/`reload` 改走选择器同步；`snap` 只在项目状态真变时把分组吸附回当前项目所在组，用户主动浏览另一组不被拽回。
- `desktop_lifecycle.py` `reload()`：`_sync_project_picker()`＋`refresh_sidebar_title()`（替代 `fill_projects(self.list)`），首页项目树照旧刷新。
- `desktop_account_page.py`：授权锁标刷新改写 `nav_label` 短编号＋' 🔒'。
- `ui_widgets.py`：新增 `RailIcon.TButton`/`Selected.RailIcon.TButton`（居中、xs 内边距）；`Nav.TButton`/`Sub.Nav.TButton` 横向内边距统一 `SPACING['xs']`/`NAV_SUB_PADDING_X`；选中态由 `primary` 实心块改为 `surface_pressed` 浅灰胶囊＋深色内容（X 桌面风格，用户明确要求）。
- `ui_tokens.py`：`DESKTOP_LAYOUT['sidebar_width']` 154→92；`NAV_SUB_PADDING_X` 26→16。
- `desktop_layout.py`：`fit_sidebar` 紧凑内边距覆盖 Nav/Selected.Nav/RailIcon/Selected.RailIcon/Sub.Nav 各变体；删除 Treeview 行数反算；`align_header` 改用 `project_block` 定位；侧栏 paint 键改用 `_picker_items` 长度。
- 文档同步：`design_tokens.md`（内边距/行高 token 表注明图标轨口径）、`ui_components.md`（图标轨与 RailIcon 说明）。
- 测试：`tests/test_ui_icons.py` 新增 `NavIconTests`——20 个语义名→PNG 契约、加载/缓存/缺失三态；account/page_lock/login_gate/batch3/compact_layout/rename_reconcile/switch_guard/sidebar_title/resize_coalescing/button_consistency 等断言随契约更新（编号+图标、选择器替代树、RailIcon 样式）。

## 契约变化说明（§2.4）

- 侧栏项目树→分组图标+选择器：`self.list`、`<<TreeviewSelect>>`、侧栏分组「展开保持」语义移除，由分组筛选钮＋选择器取代；首页项目树（`_project_home_tree`）不变。
- 选中态配色：`Selected.Nav/Sub.Nav` 由 primary 实心改 `surface_pressed` 浅灰胶囊（用户明确要求 X 风格）。
- `test_desktop_startup_perf.test_real_project_page_callback_is_interactive`：过渡状态断言增加「还缺必填：…」——图标轨使 `reload()/load()` 变快后，发送门禁 `after(250)` 防抖可落在「正在打开剧本准备…」之后触发；该提示是真实页面状态而非假加载，核心契约（不得伪装「正在载入今日项目…」、最终回到项目路径）未弱化。
- `test_desktop_compact_layout`：RailIcon 断言兼容 `Selected.RailIcon.TButton` 变体；`compound` cget 在本机 Tk 返回 index 对象，断言经 `str()` 归一。
- `test_project_rename_reconcile`：两处 `read_text()` 补 `encoding='utf-8'`（既有 GBK 环境 bug，与本次 UI 无关，顺手修复）。

## 环境修复与解释器说明（非本轮源码改动，如实记录）

- 本工作树 3 个 gitlink 嵌套仓库只有空目录占位，已从主工作区按记录 SHA clone 补齐：`reference/HoLLMwood`(3ef9f99)、`skills/00全流程SKILL/AIGC创作全流程`(1a43ae5)、`skills/01 剧本准备SKILL/剧本锻造`(6c3d739)。补齐前 `test_idea_chat*`、`test_workflow_writing_stages`、`test_writing_api_output_budget`、`test_claude_writing_session` 因 SKILL.md 缺失报红，补齐后复验转绿。
- 工作树缺 `运行环境\Python`，早期定向测试误用系统 Python 3.14.7；钉版解释器为主工作区 `运行环境\Python`（3.15.0）。已用钉版解释器复跑核心 GUI 定向集（见「验证」）。`test_claude_writing_session.test_separate_confirmations_do_not_share_dispatch_signature` 在 3.14 下确定性红：`date.today()` 在 3.14 会消耗 `patch('desktop.time.time', side_effect=[100,101])` 的配额（3.15 不经该属性），属解释器版本差异，与本次改动无关（该测试用 SimpleNamespace，不触桌面侧栏）。

## 三问

- 本轮属于 §3.1 功能轮。
- 测试跑了：`smoke_test.py` 默认冒烟 8/8 绿；`smoke_test.py --affected desktop ui_widgets ui_tokens ui_icons desktop_page_registry` 的门禁步（run_selftests 134 文件 serial）在 900s 超时截断，已跑部分除上述环境旧账（补齐后复验绿）外全绿；超时未覆盖的文件与全部定向项以补跑 `-k` 结果为准（见下「验证」）。
- `project_status.md` 欠账：无新增；分支轮不抬轮次头，合并轮推进。

## 验证

- 默认冒烟：`smoke_test.py` 8/8（钉版 Python 3.15.0 复跑同绿）。
- 架构门禁：affected 内 `architecture.test_*` 12 个文件全绿（含 `test_ui_icons_boundary`、`test_tooltip_boundary`、`test_source_text_contracts`）。
- 钉版解释器（`运行环境\Python` 3.15.0）核心 GUI 定向集 **129/129 全绿**：`compact_layout`/`resize_coalescing`/`button_consistency`/`account_entry`/`account_page`/`page_lock`/`login_gate`/`ui_batch3_shell`/`rename_reconcile`/`switch_guard`/`sidebar_project_title`/`ui_icons`/`startup_perf`/`page_cache`/`paint_freeze`＋`architecture.test_ui_icons_boundary`；另 `test_claude_writing_session` 11/11 绿。
- `smoke_test.py --affected desktop ui_widgets ui_tokens ui_icons desktop_page_registry` 门禁步（run_selftests 134 文件 serial）900s 超时截断；已跑部分除环境旧账（gitlink 缺失→补齐复验绿；3.14 解释器差异→3.15 复验绿）外全绿；超时未覆盖文件由补跑 `-k`（371 条）覆盖，除上述两类环境项外全绿。
- 全量回归：本轮未跑 `--all --safe`（功能分支轮；启动路径/Tk 生命周期改动的当次全量由合入 master 前的合并轮触发）。最近凭据：R2811（2026-11-15，393.67s，tree 8509b4f7）。

## 提交

待补：commit hash 由 dev.py commit 回执填写。
