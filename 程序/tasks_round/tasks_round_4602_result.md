# R4602 轮次结果（S04-W4：S04 主页左右分栏工作台融合、时间线筛选与任务书收尾）
<!-- round-evidence: {"commit_base": "46cd3546b", "credential_hits": 0, "evidence_sha256": "042a0bb7d838c946", "exit": 0, "failed": 0, "passed": 222, "round": 4602, "tests": "run_selftests.py -k animatic_page ui_edges_pages copy_rules taskbook_closure requirement_traceability http_boundary text_component_boundary layer_relations module_size_ratchet button_boundary ui_icons_boundary dialog_boundary complexity_ratchet"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮＋任务书收尾闭环（执行《分镜预演工作台与管理预览审核改造任务书》卡 `S04-W4`，落地 `REQ-S04-116` 与 `DES-S04-39`，同步完成整体验收与任务书闭环文件）。
- **测试跑了吗、三个基线过了吗**：已运行——隐藏桌面 3 套 UI 套件（`test_animatic_page`、`test_ui_edges_pages`、`test_files_panel_stages`）344/344 通过（245.37s），修正文字样式后复验 `test_animatic_page` + `test_animatic_page_low_button_layout` 90/90 通过（17.72s）；业务与文案 6 组 132/132 通过（16.77s）；默认冒烟 `smoke_test.py` 9/9 通过；完整架构门禁 `smoke_test.py --architecture` **714/714 通过**（284.29s）；任务书闭环校验 `scripts.taskbook_closure.validate()` 返回 `[]`；未运行整仓 `--all --safe`（本分支改动已全部覆盖受影响套件与全套 714 项架构门禁，分支按 `AGENTS.md` §5 不累计主干全量欠账，合入 `master` 时按合并出口门禁执行）。
- **欠账少了吗**：`REQ-S04-116`／`DES-S04-39` 翻绿为 ✅，本任务书 4 张卡（`REQ-S04-114`…`117`、`DES-S04-37`…`40`）全部闭环；`ui/animatic_page.py` 906/1000（较基线 944 反而净减 38 行）、`ui/animatic_view_state.py` 881/1000，全部严守 1000 行红线；零新增架构门禁或文案欠账。

## 改动清单

- `程序/ui/animatic_view_state.py`（881 行 ≤1000，零新增 L4 同层边）：
  - 新增 `animatic_viewport_split(win)`（宽屏 `>=1200px` 且非紧凑高度返回 `True`）并接入 `animatic_layout_metrics(win)['split']`。
  - 新增 `SCENE_ALL_LABEL`、`TIMELINE_STATUS_FILTERS`、`EMPTY_GUIDE_STEPS`、`scene_filter_options(board)`、`filtered_timeline_shots(state)`、`shot_cell_caption(row)`。
  - 下沉无 Tk 异步派发与动作辅助（`_update_summary`、`_locked`、`_lock_finished`、`_reclassify`、`_rename_reference`、`_apply_sketch`、`_after_sketch`、`_open_shot_dir`、`_import_references_dialog`、`_dispatch_generate`、`_dispatch_redo_shot`、`_dispatch_redo_revisions`、`_dispatch_lock`、`_register_send_key_impl`）。
- `程序/ui/animatic_page.py`（906 行 ≤950）：
  - 接入页顶 5 入口 `animatic_toolbar` 与上半区右栏 `animatic_inspector`；宽屏 `>=1200px` 左右并排、窄屏 `<1200px` 自动上下堆叠（受 150ms `<Configure>` 防抖保护）。
  - 左栏无视频时展示 3 步空态引导卡并保留右键菜单；有视频后点选时间线任意镜头或按 `←`/`→` 键实时刷新右栏选中镜大图与元信息，左栏封面不变（打破封面锁死）。
  - 时间线上方新增紧凑筛选条（场次下拉＋状态筛选「全部／需修改／对白超长／缺草图」＋「重做全部需修改」按钮，独立于 `timeline_box` 守住分页边界）；镜头格附紧凑审核角标，保持 20 镜/页分页渲染与全部旧右键／底栏发送键／离页释放逻辑。
- `程序/ui/animatic_inspector.py`（257 行 ≤380）：联动将 3 处手写 `font=` 标签迁移至 `Tokens.Title.TLabel` 与 `HintLabel`，满足 `test_text_component_boundary`。
- `程序/docs/process/外部依赖清单.md`：同步 `orchestrator/stage_animatic_gateways.py` 既有本机 ComfyUI 地址行号（157→174，因 `R4596` 新增函数下移），通过 `test_http_boundary`。
- `程序/tests/test_animatic_page.py`、`程序/tests/test_ui_edges_pages.py`：新增 `WorkbenchFusionTests`（3 条，锚定 `REQ-S04-116`）并按 §2.4 同步低按钮与 3000 镜恒定控件基线断言。
- `程序/docs/stages/S04_分镜预演.md`、`程序/docs/records/对话需求追溯.md`、`程序/tasks_round/分镜预演工作台与管理预览审核改造任务书.md`、`程序/tasks_round/任务完成/分镜预演工作台与管理预览审核改造·任务完成.md`：翻绿 `REQ-S04-116`／`DES-S04-39`、更新交互章节与测试锚定、勾选 §5 并输出同名任务完成文件。

## 既有测试契约变更说明（AGENTS.md §2.4）

因用户 Q2/Q5/Q6 拍板（`REQ-S04-116`）将页顶 5 入口工具条、右栏镜头检查器与时间线筛选条纳入 S04 常驻控件，同步以下三处依赖旧「单按钮／无工作台控件」契约的断言，未弱化性能或未生成确认条红线：
1. `程序/tests/test_ui_edges_pages.py` L100–136（`test_animatic_page_low_button_layout`）：由旧的整页按钮 ≤1 同步为断言页顶工具条顶级入口 ≤5、未生成视频前仍无页底确认勾选框。
2. `程序/tests/test_animatic_page.py` L358–364（`LayoutTests.test_layout_hooks_and_summary`）：同上，校验页顶工具条存在且顶级入口 ≤5、未生成视频前无确认勾选框。
3. `程序/tests/test_animatic_page.py` L1384–1406（`test_3000_shots_keeps_widget_count_bounded`）：新增恒定常驻工作台控件（工具条＋检查器＋筛选条）后，21 镜与 3000 镜总控件数均恒定为 166；将断言同步为既验证 `total_3000 == total_21`（精确 O(1) 零增长）又验证 `<= 180`。
4. `程序/tests/test_animatic_page.py` L1581–1605（`DebounceAndPanelPerfTests`）：新增 `_settle_initial_map()` 先完成首次窗口映射并清空初始建页防抖定时器，再启动 `<Configure>` 150ms 防抖与销毁取消测量，避免 8 路并行隐藏桌面下首次建页映射耗时（~83ms×并发）挤占 150ms 防抖窗口，原 150ms 防抖与销毁零重绘断言未弱化。

## 先红后绿证据

改动 `ui/animatic_page.py` 前先更新测试并运行 `LayoutTests.test_layout_hooks_and_summary` 与 `WorkbenchFusionTests`，实测 **Ran 4 tests in 1.435s, FAILED (failures=4)**：
- `test_layout_hooks_and_summary`：`AssertionError: unexpectedly None : REQ-S04-116：应构建页顶紧凑工具条`
- `test_req_s04_116_clicking_shot_updates_inspector_without_locking_by_video_cover`：尚未构建右栏检查器
- `test_req_s04_116_timeline_filters_redo_revisions_and_lock_guard`：`AssertionError: False is not true`（无审核角标与筛选条）
- `test_req_s04_116_wide_split_narrow_stack_geometry_and_cleanup`：`AssertionError: '生成分镜预演' not found`（无 3 步空态引导与左右分栏）

改动后全部转绿：隐藏桌面 3 套 UI 套件 344/344（复验 90/90）、业务与文案 6 组 132/132、默认冒烟 9/9、完整架构门禁 714/714、`taskbook_closure.validate()` 返回 `[]`。

## 活跃车道避让说明

`程序/docs/records/会话接续记录.md` 末尾正被活跃分支 `codex/master-regression-repair`（最新提交 `3a8910abb`）追加修改，直接修改会与该活跃车道产生真实合并冲突；按 `R4595` 先例本分支主动错开不改，全部交接与验收凭据已完整留痕于本结果文件与同名任务完成文件，待合入 `master` 时补记。

## 提交状态

- 工作树：`D:\漫剧制作助手\.agents\worktrees\s04-workbench-spec`
- 分支：`codex/s04-workbench-spec`（未 `git push`，待用户拍板合入 `master`）
- 提交方式：经 `scripts/dev.py commit` 提交。
