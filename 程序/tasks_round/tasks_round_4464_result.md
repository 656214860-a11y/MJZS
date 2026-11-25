# tasks_round_4464_result — DOC-S03 S03 阶段文档补接口与交互两节
<!-- round-evidence: {"commit_base": "1f66bd04d", "credential_hits": 0, "evidence_sha256": "2462230c749d5af2", "exit": 0, "failed": 0, "passed": 0, "round": 4464, "tests": "docs-only"} -->

## 三问

1. 本轮类型：§3 之外的任务卡轮——纯文档轮（DOC-S03，W2），只改 `docs/stages/S03_初步分镜.md` 与本结果文件，未改任何 `.py`。
2. 测试：按卡面跑三项验收。① `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`：34 用例 0 红，退出码 0；② `smoke_test.py --architecture`：708 用例全绿，退出码 0；③ `smoke_test.py`：9 项通过 0 失败，退出码 0。
3. 欠账：无新增欠账；文档与代码不一致处记入下方差异清单，未顺手改既有 REQ/DES 条目。

## 改动

`docs/stages/S03_初步分镜.md` 末尾（行 137 测试锚定表之后）追加 `## 接口`（读入 19 行 IF-S03-01~19、写出 15 行 IF-S03-20~34、完成判定与交接 13 行 IF-S03-40~52、对外调用 5 行 IF-S03-60~64）与 `## 交互`（页面区域 5 块＋共用部分说明段、控件与操作 23 行 UX-S03-01~23、页面状态 8 行 UX-S03-60~67、键盘右键拖放 14 行 UX-S03-80~99）。编号段内从小到大，无重复无跨节；既有 `### 接口（S03 发送，✅）`／`### 交互与验收` 小节（`## 设计` 下）保留未动。`git diff --numstat`：146 增 0 删，仅新增行。

## 读过的文件清单（核实依据）

规范与验收：
- `docs/process/阶段文档写法.md`；`tests/architecture/test_stage_doc_sections.py`；`docs/stages/S01_剧本准备.md`（已过检样例）；`docs/stages/S03_初步分镜.md` 全文；`tasks_round/工程文档细化任务书.md` §4.9。

页面构建与控件（交互节来源）：
- `desktop.py:844` `storyboard_creation`→`ui.storyboard_files.show`；`ui/storyboard_files.py` 全文（`_StoryboardFilesPage`：`_init_page_state`/`_build_editor`/`_register_storyboard_send_action`/`_register_files_panel_handler`/`show_document`/`_render_active_document`/`_update_status_segment`/`begin_edit`/`exit_edit`/`save_edited`/`toggle_json_view`/`apply_catalogs`/`refresh`/`apply_background_catalog`/`renumber_shots`/`browse`/`adopt_selected`/`remove_selected`/`restore_latest`/`watch_files`/`document_dir`）；`ui/storyboard_table_ui.py` 全文（`S03EditorView`/`S03ShotNavigator`/`render_document_text`/`pick_default_document`/`format_storyboard_for_editor`/`extract_storyboard_shots`，常量 `S03_EMPTY_TEXT`/`S03_HINT_READ`/`S03_HINT_EDIT`/`_SHOT_NAV_WHEEL_LINES`/`VIEWER_WHEEL_LINES`）；`ui/desktop_page_nav.py`（`storyboard_creation` 注册）；`ui/desktop_status_bridge.py:55` `set_status_segment`；`ui/desktop_files_panel.py`（`set_select_handler`）。

发送链与门禁（接口节来源）：
- `desktop_shared_send.py`：`send`/`_send_free`/`_send_skill`/`_send_empty_storyboard`/`send_storyboard`/`upstream_send_error`/`_account_block`/`host_options`/`make_shared_input`；`desktop_shared_input.py` `SharedStageInput`（`text`/`request_snapshot`/`request_model`/`in_flight`/`_drafts`/`set_stage_action`）；`stage_handler_registry._start_storyboard`；`stage_run_action`/`skip_unchecked`；`ui/desktop_direct_dispatch.py`；`ui/desktop_idea_chat.py:721` `open_flow_agent`。

选择／采用／完成核验：
- `orchestrator/storyboard_selection.py`（`selected_many`/`remember_many`/`choose`/`adopt`/`remove`/`focus`/`adopted`/`current_source`/`sync_working_episode`/`repair_working_episode`/`adopt_pending`/`poll_auto_adopt`/`prune_invalid_adoptions`/`sync_draft_outputs`/`draft_problems`/`source_script_error`/`summary`）；`orchestrator/storyboard_page_controller.py`（`refresh_catalogs`/`apply_catalogs`/`latest_recycle_batch`/`restore_latest`/`prune_invalid_adoptions`）；`orchestrator/stage_asset_gateways.py:64-76`（`adopt_asset_storyboards`）；`orchestrator/stage_execution_service.py:732-762`（`save_edited_stage_storyboard`/`publish_final_storyboard_bundle`/`normalize_storyboard_for_desktop`）＋`adopt_frame_jsons`/`remove_frame_jsons`/`storyboard_adoption_impact`/`import_json`/`sync_working_episode`/`final_storyboard_hint`/`shot_numbering_hint`；`orchestrator/stage_previs_gateways.py:54-122`（`storyboard_catalog`/`produced_scripts`/`produced_episodes`/`default_source`/`resolve_source`/`board_source_script`/`working_dir`/`document_dir`/`file_snapshot`/`catalog_snapshot`）；`orchestrator/stage_handoff_gateways.py:210`（`storyboard_adoption_impact`）；`orchestrator/stage_completion_service.py`（`completion_evidence`/`storyboard_send_readiness`/`emit_verified_completion`）；`orchestrator/storyboard_direct_api.py`（`direct_model`/`run_batch`/`launch`/`_ask`/`_validated`/`_failure`/`_markdown`）；`orchestrator/storyboard_recycle_service.py`（`RECYCLE_REASON='分镜页删除'`/`recycle_plan`/`recycle_files`/`latest_recycle_batch`/`restore_latest_recycled_files`/`detach_video_refs`）。

域与契约层：
- `domain/storyboard_catalog_service.py`（`catalog`/`file_snapshot`/`default_source`/`resolve_source`/`storyboard_working_source`）；`domain/storyboard_plan_service.py`（`storyboard_work_plan`/`build_work_plan`）；`domain/storyboard_adoption_contract.py`（`adopted`/`resolve_source`/`check_adoptable`）；`domain/storyboard_storage.py`（`normalize`/`normalize_for_desktop`/`resolved_alias`/`canonical_name`/`snapshot`/`_references`）；`domain/asset_plan.py` `_sync_plan`；`ui/shot_numbering.py`（`renumber`/`verify`/`storyboard_order`）；`stage_parallel.py`（`CONFIG['storyboard']`/`GATES`/SG-A `animatic_input_ready`/`EXEMPT_STATES`/`stage_state`/`_adopted`）；`workflow_settings.py`（`resolve_for_send`/`current`/`skill_prompt`/`_named_skill_config`）；`workflow_tasks.py`（`storyboard_batch_prompt`/`storyboard_batch_plan`/`storyboard_direct_rules`/`STORYBOARD_SAVE_RULE`）；`contract/episode_contract.py` `validate_episode`；`contract/storyboard_paths.py` `media_root`；`contract/script_contract.py`（`structured_script_paths`/`is_structured_script`/`structure_manifest_problems`/`STAGE_LOCK_REQUIREMENTS`）；`contract/project_stages.py`（`writing`）；`contract/platform_tools.py` `open_directory`；`infra/pet_state.py`（`STAGES`/`PAGE_OF`）；`infra/storage_maintenance.py` `recycle_paths`；`infra/model_metering.py` `chat_metered`；`infra/business_log.py` `log_event`；`infra/file_cache.py` `read_text`；`domain/writing_api.py` `WritingRequestAdapter`；`agent/core.py`（`save`/`save_text`/`read`）；`projects.py` `create`。

## 控件数对照

构建代码中的可操作控件（`ui/storyboard_table_ui.py` + `ui/storyboard_files.py`）：

- `S03EditorView._build`：主编辑 `TextArea`（`undo=True, maxundo=-1`）＋垂直滚动条 1 条。
- `S03ShotNavigator.__init__`：检索框 `LineInput`（`placeholder='搜镜头号/角色/场景…'`）＋镜头列表 `TextArea`＋滚动条 1 条（「镜头定位」标题与计数 `count_label` 为显示件）。
- `S03EditorView._build_find_bar`：查找框 `LineInput`（`placeholder='查找镜头、角色、对白或提示词…'`）＋「上一个」「下一个」「关闭」3 个 `SecondaryButton`（`find_count` 为显示件）。
- `S03EditorView.popup_context_menu`：右键菜单命令 15 个——「退出编辑并保存」「立即保存 (Ctrl+S)」「编辑当前文档」「切换为分镜阅读视图／切换为原始 JSON」「取消采用当前分镜／采用分镜」「导入 JSON 分镜…」「选择其他剧本…」「重排镜头编号」「显示镜头定位 (Ctrl+G)／隐藏镜头定位 (Ctrl+G)」「查找 (Ctrl+F)」「打开其他文件… (Ctrl+O)」「打开分镜目录」「刷新分镜列表」「恢复最近删除」（前 5 组按编辑态/文档类型/采用态条件显隐，实际同时可见 ≤13 项）。
- 可操作控件合计 7 个（viewer、镜头检索框、镜头列表、查找框、3 按钮）＋菜单命令 15 个＝22 个；滚动条 2 条、计数/标题/快捷键提示 Label 4 个为附属显示件。

控件表行数：UX-S03-01~23 共 23 行＝7 个可操作控件各 1 行＋15 个菜单命令各 1 行＋1 条「过程与回话区」目标行（UX-S03-23）。滚动条与显示件并入宿主行，未单列；逐行核对无漏项、无多列项。

## 差异清单（文档 vs 代码，不改既有条目）

1. `storyboard_table_ui.py` 仍保留 `file_table`/`insert_entries`/`fit_file_columns`/`fit_final_columns`/`tree_columns` 双表工具，仅被 07 分镜定稿页 `_FinalStoryboardPage`（`storyboard_files.py:571`）使用；S03 页为单编辑器，未用双表。
2. `VIEWER_SAVE_ASK_MS=900` 与 `ask_save_soon`/`ask_save` 属 `_FinalStoryboardPage`（07 定稿页的去抖「保存询问」）；S03 页 `save_edited` 立即校验落盘、无询问窗。
3. 「恢复最近删除」恢复对象是经共享文件面板删除链产生的 `分镜页删除` 批次（`storyboard_recycle_service`）；S03 页自身右键菜单没有「删除」项。
4. `browse()` 的 `FileDialog` 初始目录为 `contract/project_stages.writing(project)`（旧剧本目录），类型限 `*.md *.txt *.docx`，非 `stage_path_service` 读目录并集。
5. `_update_status_segment` 的状态段 tooltip 恒为 `S03_HINT_READ`，不随编辑态切换。

## 待裁决清单

- 「过程与回话区」1 条 ⬜：页面区域第 5 块与 UX-S03-23，来源：用户决定 2026-11-21；细节见专题册 08。除此外无 🟡/❓ 项。

## 验收

- `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（cwd `程序/`）：4 个测试文件 34 用例，`ALL TESTS PASSED`，退出码 0。
- `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：`Ran 708 tests in 347.587s`，`OK`，退出码 0。
- `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py`：通过 9 项 / 失败 0 项，退出码 0。
- `git diff --numstat -- 程序/docs/stages/S03_初步分镜.md`：`146	0	程序/docs/stages/S03_初步分镜.md`，仅新增行、已有 137 行零删改。

## 未验证项

- `storyboard_direct_api` 的回退候选细节只核到 `_ask`/`group_candidates`/`PoolAdapter`/`chat_metered` 调用点，`PoolAdapter` 内部未逐行读。
- `stage_publication.publish_stage_bundle` 的 `allowed` 守卫只核到调用签名与契约名，未逐行读实现。
- `agent_skill_sync.sync_agent_skills`（技能文件同步进引擎目录）未列为对外调用：它是本地文件写入非网络服务，细节未逐行核。
- `FinalStoryboardController.save_edited` 的校验细节核到 `save_edited_stage_storyboard`/`storyboard_edit_service`/`storyboard_edit_gateway` 门面名，内部未逐行读。
