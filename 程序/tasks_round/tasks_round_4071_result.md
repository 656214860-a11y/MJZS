# R4071 结果：连贯性清单阶段文档补「接口」「交互」两节（DOC-S06）
<!-- round-evidence: {"commit_base": "5589df12", "credential_hits": 0, "evidence_sha256": "1c350f6791955c2b", "exit": 0, "failed": 0, "passed": 10, "round": 4071, "tests": "run_selftests.py -k stage_doc_sections"} -->

## 开头三问

1. **本轮类型**：文档轮（任务卡 DOC-S06，《工程文档细化任务书》§4.9）。未修改任何 `.py` 文件。
2. **测试与基线**：文档轮不跑默认冒烟与全量（均未运行）；任务卡验收命令 `python -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 已跑：4 个测试文件共 34 条用例全过、0 个文件有红、输出 `ALL TESTS PASSED`、退出码 0，跑 1 轮即过。
3. **欠账**：本轮无新欠账。

## 改了什么

卡 B-DOC-S06（波次 W2，车道 codex/doc-stages-b，基准 5589df12）：给 `docs/stages/S06_连贯性清单.md` 末尾追加了「## 接口」「## 交互」两节，原有 96 行一字未动（`git diff --numstat` 新增 92、删除 0）。另新建本结果文件 `tasks_round/tasks_round_4071_result.md`。除此之外没有改任何文件。

各小节行数（含三级标题、表头、空行）：

- `### 读入`：13 行（9 条数据，IF-S06-01…09）
- `### 写出`：11 行（7 条数据，IF-S06-20…26）
- `### 完成判定与交接`：12 行（8 条数据，IF-S06-40…47）
- `### 对外调用`：5 行（1 条数据，IF-S06-60；无对外调用说明行）
- `### 页面区域`：11 行（9 个列表项，不编号）
- `### 控件与操作`：13 行（9 条数据，UX-S06-01…09）
- `### 页面状态`：12 行（8 条数据，UX-S06-60…67）
- `### 键盘、右键与拖放`：3 行（无编号行，按卡面写「本页没有专门的键盘、右键、拖放操作。」）

状态记号分布（合计 42 行编号行）：✅ 40 行、⬜ 1 行（UX-S06-09，卡面指定目标行）、🟡 0 行、❓ 1 行（UX-S06-62）。

## 读过的文件清单

写法与守卫：`docs/process/阶段文档写法.md`（全文）；`tests/architecture/test_stage_doc_sections.py`（全文含 `_COMPLIANT`）；`docs/stages/S06_连贯性清单.md`（全文）；`docs/stages/S05_资产管理.md`（只看「接口」「交互」两节写法与详略）；`tasks_round/tasks_round_4068_result.md`（结果文件格式样例）。

页面与交互：`ui/desktop_media_pages.py:210-450`（`write_continuity_ledger` 213、`generate_continuity_ledger` 217、`pet_continuity_ledger` 230、`pick_gate` 调用点 333-335、`continuity_folder`、`continuity_page` 234-341、`continuity_issue_rows` 342、`sync_continuity_issues`、`ignore_continuity_issue`、页头/`table_of`/`open_detail`、`current_frame_json` 438-446）；`ui/storyboard_source_selector.py:1-81`（全文）；`ui/desktop_page_nav.py:120-209`；`ui/desktop_pet_bridge.py:60-89`；`ui/pet_ui_stages.py:15-17`；`ui/desktop_automation_tick.py`（`pick_gate` 235 起与 `auto_decide_gates`）；`ui/desktop_asset_pages.py:348-366`（`asset_scope`/`asset_requirements`）；`desktop.py:557-567,807-814`（`safe`/`note`）；`orchestrator/page_navigation_controller.py`（`decide`/`needs_source_selector`）。

L2/L3/契约：`infra/continuity_ledger.py`（全文重点：`build`/`publish_bundle`/`write`/`read`/`ledger_path`/`issues_path`/`read_issues`/`merge_issues`/`sync_issues`/`decide_issue`/`issue_gate`/`open_problems`/`stale_reason`/`final_block_reason`/`require_final_ready`/`markdown`/`_anchor_library`/`_triplet_rows`）；`continuity_ledger.py`（兼容门面，全文）；`domain/confirm_gates.py`（`run`/`conflict_candidates`/`adjudicate`/`pending`/`record`/`forget`/`confirmations`/`confirm_path`/`state_of`/`OPTIONAL_GATES`/`check_drift`）；`domain/stage_path_service.py`（`write_dir`/`read_dirs`/`read_file`/`LEGACY_NUMBERED`）；`domain/asset_plan.py:230-242`（`apply_asset_plan_gate_choice`）；`orchestrator/stage_parallel.py`（`CONFIG`、`GATES` 518-538、`BROWSE`/`PRODUCTION` 555-587、`blocked_text` 605-613、`stage_state`/`has_run` 616-631、`_current_shots`、`assets_locked` 690-754、`ledger_ready` 757-777、`evaluate` 924-932、`page_lines` 969 起）；`orchestrator/stage_flow.py:34-50,77,110-154`（`RUNNING_LABEL`/`MANUAL_RUNNING_LABEL`/`PAID_STAGES`/`unchecked`/`button_text`/`apply_text`/`RECOVERY_HINTS`）；`orchestrator/stage_handler_registry.py:26-41,104-153`；`orchestrator/stage_handoff_gateways.py:222-244`（`continuity_issue_report`/`sync_continuity_issues`/`decide_continuity_issue`）；`orchestrator/storyboard_selection.py:22-24,96-141`；`orchestrator/stage_completion_service.py:730-789`（`completion_evidence`，`'continuity': 'ledger_ready'` 分支 783-788）；`orchestrator/media_page_controller.py`（`summary_text`/`build_ledger`/`continuity_folder`/`batch_rows`/`check_rows`/`issue_table_rows`/`open_issues`）；`stage_execution_service.py`（`sync_asset_plan`、`record_stage_confirmation`/`forget_stage_confirmation`、`stage_context` 与发布器注入面）；`pet_agent.py:822-840`（`gate`）。

## 控件数对照

- 构建代码里创建的可操作控件（按种类）：`continuity_page` 内 `…Button(…)` 创建点 4 处——固定「手动生成连贯性清单」「清单目录」＋按未决 G-08 候选逐条创建的「采用推荐」＋按待处理问题逐条创建的「忽略（写明理由）」；`table_of` 创建 `DataTable` 3 处（「问题闭环」表仅在有登记问题时创建，「跨批次与三元组校验」表末列与「问题闭环」表末列各绑定一次可点「说明／证据」格）；另有 `desktop_page_nav.show` 经 `source_selector` 注入的「选择分镜」下拉框 1 处。合计 8 类。
- 「控件与操作」表 9 行：8 行事实行与上述 8 类一一对应（2 固定按钮、3 表、2 类动态按钮、1 注入下拉框各一行），另 1 行为卡面指定目标行 UX-S06-09。

## 差异清单

文档已有条目与代码对不上的地方：

1. REQ-S06-33／DES-S06-33 写「fallback `_start_unattended_stage` 新增 continuity 分支」；代码里 continuity 分支实际在 `_execute_unattended_stage`（`ui/desktop_pet_bridge.py:77-78`），`_start_unattended_stage` 只转 `pet_ui_stages.stage_run_action`（`ui/pet_ui_stages.py:15-17`），语义等价但函数名差一跳。
2. 「设计／模块分工」L2 行列 `continuity_ledger`：实现主体在 `infra/continuity_ledger.py`，根目录 `continuity_ledger.py` 只是转发门面（`程序/continuity_ledger.py` 全文）。
3. 「设计／模块分工」L2 行列 `skill_tools`：`continuity.*` 工具实际登记在 `ui/skill_tools.py`（`_continuity_ledger` 455、`continuity.buildLedger` 521），不在 L2 层文件。

代码侧观察（不属于文档差异，照实记录供总控定夺）：`domain/confirm_gates.py` 的确认账本注释与旧路径回退仍沿用旧阶段别名 `03_continuity`（经 `stage_layout.LEGACY_STAGE_ALIASES` 映射到 `06连贯性清单`），属遗留命名。

## 待裁决清单

- UX-S06-62（❓）：前置阶段没完成（SG-01 未过）时，本页照常建页、现场算台账，「手动生成连贯性清单」也不核验 SG-01（`continuity_page`／`generate_continuity_ledger` 只查有无镜头；SG-01 只经 `pet_agent.gate`→`stage_parallel.evaluate` 拦自动链）。可选方案：a) 保持现状——页面显示的待办已能反映上游缺漏，入口闸归自动链；b) 在手动生成入口按 `stage_parallel.evaluate` 口径提示或拦截——需总控定。

## 没做的

- 默认冒烟与全量回归未运行（文档轮不跑）；验收命令 `python -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 已跑：34 条用例、0 个文件有红、退出码 0，1 轮即过。
- `git push`／合入未执行。
- 「设计」节引用、但本轮没有逐行读的代码：`contract/shot_batches.py`（`triplets`／`continuity_flags` 归并，DES-S06-14/15）、`contract/artifact_schema.py`（`stamp`）、`contract/stage_layout.py`（`anchors_path`/`triplets_path`/`LEGACY_STAGE_ALIASES`，仅经 grep 定位）、`ui/skill_tools.py:455-521`（`continuity.*` 工具登记，仅经 grep 定位两行）、`skills/06连贯性SKILL/` 与 `workflow_settings` 预设（DES-S06-30/32）、`ui/desktop_automation_tick.py` 的 `auto_decide_gates` 全文（只读 `pick_gate` 附近）、`stage_execution_service.py` 仅读点名函数附近。
- 没改 `docs/stages/S06_连贯性清单.md` 的「需求」「设计」两节与既有任何字符（追加纯新增，删除数 0）；没改允许清单（阶段文件＋结果文件）以外的任何文件。
