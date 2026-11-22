# R4085 结果：分镜定稿阶段文档补「接口」「交互」两节（DOC-S07）
<!-- round-evidence: {"commit_base": "293ff92a", "credential_hits": 0, "evidence_sha256": "d30c10ae26b7c3fb", "exit": 0, "failed": 0, "passed": 10, "round": 4085, "tests": "run_selftests.py -k stage_doc_sections"} -->

## 开头三问

1. **本轮类型**：文档轮（任务卡 DOC-S07，《工程文档细化任务书》§4.9）。未修改任何 `.py` 文件。
2. **测试与基线**：文档轮不跑默认冒烟与全量（均未运行）；任务卡验收命令 `python -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 已跑：4 个测试文件共 34 条用例全过、0 个文件有红、输出 `ALL TESTS PASSED`、退出码 0，跑 1 轮即过。
3. **欠账**：本轮无新欠账。

## 改了什么

卡 B-DOC-S07（波次 W2，车道 codex/doc-stages-b，基准 293ff92a）：给 `docs/stages/S07_分镜定稿.md` 末尾追加了「## 接口」「## 交互」两节（110 行新增）；另按接口契约第（11）条把「设计／模块分工」表里 `desktop` 那一行的层级由「L5/L4」改正为「L4」，依据是 `tests/architecture/_layers.py:64` 把 `desktop` 登记在第 4 层、`tasks_round/L5入口层诊断报告.md`「文档位置」表把 `docs/stages/S07_分镜定稿.md:70` 列为不一致。`git diff --numstat` 对该文件：新增 111、删除 1（删除数正好是那一行）。除此之外没有改任何文件；另新建本结果文件 `tasks_round/tasks_round_4085_result.md`。

第（11）条改动在 `git diff -U0` 里的原文：

```
-| L5/L4 | `desktop`（`make_final_storyboard`／`apply_final`） | 手动“手动同步资产”入口、定稿后收尾；只注入回调 |
+| L4 | `desktop`（`make_final_storyboard`／`apply_final`） | 手动“手动同步资产”入口、定稿后收尾；只注入回调 |
```

各小节行数（含三级标题、表头、空行）：

- `### 读入`：17 行（12 条数据，IF-S07-01…12）
- `### 写出`：14 行（9 条数据，IF-S07-20…28）
- `### 完成判定与交接`：16 行（11 条数据，IF-S07-40…50）
- `### 对外调用`：7 行（2 条数据，IF-S07-60…61）
- `### 页面区域`：12 行（7 个有序列表项＋「共用部分不在本文件」一句）
- `### 控件与操作`：15 行（10 条数据，UX-S07-01…10）
- `### 页面状态`：15 行（10 条数据，UX-S07-60…69）
- `### 键盘、右键与拖放`：9 行（3 条数据，UX-S07-80…82＋一句无右键拖放说明）

状态记号分布（合计 57 行编号行）：✅ 56 行、⬜ 1 行（UX-S07-10，卡面指定目标行）、🟡 0 行、❓ 0 行。

## 读过的文件清单

写法与守卫：`docs/process/阶段文档写法.md`（全文）；`tests/architecture/test_stage_doc_sections.py`（全文含 `_COMPLIANT`）；`docs/stages/S07_分镜定稿.md`（全文）；`docs/stages/S06_连贯性清单.md`（只看两节写法与详略，内容未照抄）；`tasks_round/tasks_round_4071_result.md`（结果文件格式样例）；`docs/process/用户沟通与要求标准.md`（全文）；`docs/records/会话接续记录.md`（末节）；`tests/architecture/_layers.py:55-79`；`tasks_round/L5入口层诊断报告.md`（「文档位置」表 S07 行）。

页面与交互：`desktop.py:550-579,795-919`（`safe`/`note`/`final_storyboard`/`make_final_storyboard`/`apply_final`/`open_folder`）；`ui/storyboard_files.py:1-657`（`_FinalStoryboardPage` 全部方法）；`ui/storyboard_table_ui.py:60-127`（`insert_entries`/`fit_final_columns`）；`ui/storyboard_source_selector.py:1-81`（全文）；`ui/desktop_page_nav.py:160-184`；`orchestrator/page_navigation_controller.py:55-152`（`decide`/`needs_source_selector`/`needs_adopted_storyboard`）；`ui/desktop_automation_tick.py:98-224`（`auto_final_scan`/`auto_final_state`/`retry_auto_final`）；`ui/desktop_auto_flows.py:70-203,324-378`（`busy_production`/`final_holding`/`_tick_auto_final`/`poll_auto_final`）；`ui/desktop_media_pages.py:425-449`（`current_frame_json`/`remember_frame_json`）；`ui/desktop_asset_pages.py:335-349`（`asset_base`）；`ui/pet_ui_stages.py:815-834`（`should_auto_run`）；`ui/pet_ui_support.py:30-54`（`AUTO_STAGE_VARIABLES`）。

管线与门禁：`orchestrator/storyboard_final.py`（全文 1-241）；`orchestrator/storyboard_final_controller.py`（全文 1-133）；`orchestrator/stage_parallel.py:60-79,515-539,750-944`（`CONFIG`/`GATES`/`ledger_ready`/`batches_ready`/`evaluate`/`blocked_stages`）；`orchestrator/stage_completion_service.py:780-794`；`orchestrator/stage_flow.py:25-159`（`MANUAL_LABELS`/`DEPENDS`/`RECOVERY_HINTS`/`apply_text`/`follow`）；`orchestrator/stage_previs_gateways.py:50-99`；`orchestrator/storyboard_selection.py:22-125,320-369`；`orchestrator/stage_config.py:70-114`；`orchestrator/workflow_settings.py:21,200`；`stage_execution_service.py:430-474,590-639`。

契约与领域：`contract/stage_layout.py:40-63`；`contract/stage_path_service.py:18-92`；`contract/shot_batches.py:30-268`；`contract/artifact_lineage.py:1-50`；`contract/platform_tools.py:350-424`；`contract/pet_bus.py:14-53`；`domain/asset_plan.py:25-214`；`domain/asset_context.py:36-85`；`domain/storyboard_lifecycle.py`（全文 1-100）；`domain/storyboard_storage.py:55-96`；`domain/storyboard_catalog_service.py:20-114`；`domain/final_service.py`（全文 1-10）；`infra/continuity_ledger.py:360-389,690-700`；`skills/07分镜定稿SKILL/`（目录清单 6 份 SKILL）。

## 控件数对照

- 构建代码里创建的可操作控件（按种类）：`_FinalStoryboardPage.build`／`_build_status_bar` 内按钮创建点 5 处——「手动同步资产」（`row_button` ＋ `Primary.TButton`）、「刷新列表」、「分镜目录」（同 `row_button`）、「立即重试」、「去第05步补资产」（`SecondaryButton`）；`DataTable` 定稿列表 1 处（`selectmode='browse'`）；`TextArea` 正文编辑框 1 处；`rebuild_nav` 动态「镜头目录」镜头号按钮一族（多于 1 镜才显示，0..N 颗）。另有 `desktop_page_nav.show` 经 `source_selector` 注入的「选择分镜」下拉框 1 处。合计 9 类。
- 「控件与操作」表 10 行：9 行事实行与上述 9 类一一对应（3 顶行按钮、2 提示条按钮、1 列表、1 编辑框、1 动态镜头按钮族、1 注入下拉框各一行），另 1 行为卡面指定目标行 UX-S07-10。

## 差异清单

文档已有条目与代码对不上的地方（只记不改）：

1. REQ-S07-50／DES-S07-50 写默认勾选 SKILL 来自 `workflow_settings` 的 `'final':['pipeline-storyboard-final']`（`workflow_settings.py:50`）；代码里 `orchestrator/workflow_settings.py:21` 的 `DEFAULT_SKILLS` 没有 `'final'` 键（该表是引擎／模型预设，非 SKILL 勾选表），默认勾选实际来自 `orchestrator/stage_config.default_entry`（`orchestrator/stage_config.py:73-80`，`skills`＝`skill_registry` 该阶段全部非 deprecated SKILL）。`skills/07分镜定稿SKILL/` 目录确为 6 份 SKILL，名单与文档一致。
2. 行号漂移（文档引用的行号与当前代码对不上，事实本身一致）：REQ-S07-01 引 `desktop.py:1758`→现 `desktop.py:875`；REQ-S07-05 引 `desktop.py:1760`→`desktop.py:877`、`desktop_auto_flows.py:352-355`→`ui/desktop_auto_flows.py:351-355`；REQ-S07-13 引 `shot_batches.py:24-48,115-145`→`contract/shot_batches.py:47-67,92-166`；REQ-S07-14 引 `shot_batches.py:199-240`→`contract/shot_batches.py:221-262`；REQ-S07-19 引 `stage_execution_service.py:906`→`stage_execution_service.py:615-618`；REQ-S07-31 引 `desktop_auto_flows.py:333-364`→`ui/desktop_auto_flows.py:324-355`；REQ-S07-41 引 `stage_completion_service.py:437-442`→`orchestrator/stage_completion_service.py:783-788`；REQ-S07-42 引 `stage_parallel.py:528,754-782`→`orchestrator/stage_parallel.py:529-531,780-808`；REQ-S07-02 引 `stage_parallel.py:525,724-751`→`orchestrator/stage_parallel.py:526-528,757-777`；接入索引 引 `desktop.py:860`→`desktop.py:873`。
3. 「设计／模块分工」`stage_execution_service` 行列 `storyboard_resolve_source`／`storyboard_working_source`：这两个名字在 `stage_execution_service` 只是转发导入（`stage_execution_service.py:34` 自 `orchestrator/stage_previs_gateways` 引入），实体在 `orchestrator/stage_previs_gateways.py:74-76`→`domain/storyboard_catalog_service.resolve_source` 与 `stage_execution_service.py:442-445`→`domain/storyboard_lifecycle.is_working_source`。语义一致，仅落点差一跳。

代码侧观察（不属于文档差异，照实记录供总控定夺）：

- `ui/storyboard_files.py:212-214` 注释仍写「阶段配置」按钮排在「手动同步资产」右边，该按钮已于 R2942 删除，注释与现行控件不符（历史注释残留，不改代码）。
- `ui/desktop_auto_flows.py:129-132`：自动定稿 worker 失败分支只写状态栏并退避 5 分钟，不落 `auto.final_error`；提示条「上一轮自动定稿失败」只在收尾（`apply_final` 异常）或轮询异常路径出现。文档已按实写。

## 待裁决清单

无（本轮无 ❓ 行）。

## 没做的

- 默认冒烟与全量回归未运行（文档轮不跑）；验收命令已跑：34 条用例、0 个文件有红、退出码 0，1 轮即过。
- `git push`／合入未执行。
- 「设计」节与需求条目引用、但本轮没有逐行读的代码：`domain/writing.py`（`validate_episode`，只经 `storyboard_final.py:156-158,222,226-228` 调用点确认）、`contract/prop_assets.py`（`normalize_shot`，`storyboard_final.py:113,116` 调用点）、`domain/storyboard_edit_service.py`（`save_edited_json`，只经 `stage_execution_service.py:598-602` 注入点确认）、`infra/storage_maintenance.py`（`recycle_paths`，`storyboard_lifecycle.py:73-74` 调用点）、`domain/script_preview_service.py`（`should_load_async`/`preview_chunks`/`LOADING_PREVIEW`，`storyboard_files.py:30,502-504` 调用点）、`domain/asset_batch_state_service.py`（`ready_asset_ids`，`desktop_auto_flows.py:75`、`desktop_automation_tick.py:113` 调用点）、`infra/pet_state.py`（`PAGE_OF`/`Machine`，仅经导入点确认）、`orchestrator/storyboard_adoption_contract.py`（`adopted`，`desktop_automation_tick.py:110` 调用点）、`domain/asset_reference_prompts.py`（`sync_reference_prompts`/`discover_reference_documents`，`asset_plan.py:156-169` 调用点）、`contract/storyboard_paths.py`（`is_final_dir`/`media_root`，`storyboard_final.py:4,107,166,168,181` 调用点）、`contract/file_naming.py`（`generate_existing`，`storyboard_final.py:9` 调用点）、`domain/project_naming.py`（`dated_path`，`storyboard_final.py:8` 调用点）、`orchestrator/skill_registry.py`（`getByStage`，`stage_config.py:75-77` 调用点）、`orchestrator/project_context_factory.py`（`project_context`，各调用点确认）。
- 文件字节级 BOM／换行符校验用了系统 `python -c`（只读字节检查：无 BOM、以换行结尾；非项目脚本，照实登记）。
