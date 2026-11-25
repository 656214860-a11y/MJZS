# tasks_round_4443_result — DOC-S01 S01 阶段文档补接口与交互两节
<!-- round-evidence: {"commit_base": "32bf89bb4", "credential_hits": 0, "evidence_sha256": "6f376a4a09657a3d", "exit": 0, "failed": 0, "passed": 0, "round": 4443, "tests": "docs-only"} -->

## 三问

1. 本轮类型：§3 之外的任务卡轮——纯文档轮（DOC-S01，W2），只改 `docs/stages/S01_剧本准备.md` 与本结果文件，未改任何 `.py`。
2. 测试：按卡面跑四项文档门禁 `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`，34 用例 0 红，退出码 0。纯文档轮未跑 smoke／全量（卡面未要求）。
3. 欠账：无新增欠账；文档与代码不一致处记入下方差异清单，未顺手改既有 REQ/DES 条目。

## 改动

`docs/stages/S01_剧本准备.md` 末尾（`## 设计` 整节之后）追加 `## 接口`（读入 19 行 IF-S01-01~19、写出 20 行 IF-S01-20~39、完成判定与交接 9 行 IF-S01-40~48、对外调用 7 行 IF-S01-60~66）与 `## 交互`（页面区域 5 块、控件与操作 29 行 UX-S01-01~29、页面状态 8 行 UX-S01-60~67、键盘右键拖放 13 行 UX-S01-80~92）。编号段内从小到大，无重复无跨节；既有 `### 接口`／`### 交互` 小节（`## 设计` 下）保留未动。

## 关键源码位置（核实依据）

页面构建与控件：
- `ui/desktop_writing_page.py:184` `_WritingPage.build`（`ensure_script_workspace` 前置→`_build_composer`→`_build_dialog`）；`:235` `_build_composer`（`idea_chat.default_brief_document`、共享输入框复用、`idea_attachment_status`）；`:265` `_build_dialog`（模型目录条+只读聊天框+绑定）；`:110` `build_script_quality_buttons` 仍定义无调用方；`:119` `update_recon_button`；`:129` `collect_recon`；`:399` `open_stage_panel`。
- `desktop_shared_input.py:572` `SharedStageInput`；`:606` `_build`（图标行布局：✦/＋/🎤 左，模型下拉+发送右）；`:950` `send`（空文本→`run_stage_action`，非空→上游门禁→`skill_command.parse_command`→`on_send`）；`:282` `_on_return`；`:274` `_on_escape`；`:470` `close_completion`；`:261` `_on_ime_probe`；`:526/536` `set_stage_action`/`run_stage_action`；`:550` `_sync_send_state`；`:600` `_drafts` 按(项目,阶段)隔离。
- `desktop_shared_send.py:905` `send` 分流；`:688` `_send_free`（script→`send_message`）；`:798` `send_skill_request`（REQ-S01-118）；`:81` `upstream_send_error`（script 放行）；`:191` `EMPTY_SEND_STAGES` 不含 script；`:930` `_attachments`；`:944` `_voice`；`:963` `host_options`；`:33` `STAGE_PLACEHOLDERS['script']`。
- `ui/desktop_idea_chat.py:447` `send_message`（`prepare_submission`→`validate_selected_skills`→`capture_request_model`→`inline_required_missing`→`receive_brief`→直连 API `_idea_api_received`／非直连 `start_script_workflow`→`open_flow_agent`）；`:363` `show_missing_idea_brief`；`:603` `submit_idea_api_request`；`:670` `interrupt_script_agent`。
- `ui/desktop_idea_bubbles.py:346` `add_bubble`（示例/notice/选择卡）；`:455` `add_bubble_actions`；`:570/597` `build_idea_model_bar`/`render_idea_model_bar`；`:630` `select_idea_model`；`:245` `copy_bubble_message`；`:264` `rewind_bubble_message`；`:289` `regenerate_bubble_message`；`:295` `delete_bubble_message`；`:309` `restore_latest_bubble_message`；`:319` `clear_bubble_view`；`:341` `guard_bubble_key`；`:536` `refresh_stream_text`。
- `ui/desktop_idea_menus.py:33` `open_bubble_menu`；`:64` `open_idea_paste_menu`；`:12` `delete_all_bubble_messages`。
- `ui/desktop_idea_attachments.py:52` `_sync_idea_ref_block`；`:128` `_idea_attachment_at`；`:157` `choose_idea_attachments`；`:170` `poll_idea_attachment_preparation`。
- `ui/desktop_files_panel.py:287` `ProjectFilesPanel.build`；`:138` `_build_stage_rail_state`（13 阶段＋⚙/♻/🗑/🗂）；`:250` `import_files`；`:57` `FilesPanelResizeMixin`；`:684` `open_script_file`；`:734` `rename_script`；`:758` `delete_script`；`:779` `adopt_script`；`:785` `unconfirm_preparation`；`:807` `confirm_document`；`:820` `script_menu`。
- `ui/desktop_writing_snapshots.py:31` `show_preparation_snapshots`；`:98` `show_partial_adoption`。
- `ui/desktop_script_pages.py:211` `start_script_workflow`；`:248` `open_script_quality`；`:265` `watch_script_quality`；`:310` `script_task_active`；`:315` `update_script_interrupt_button`；`:340` `refresh_script_workspace`；`:404` `import_script_downloads`；`:419` `auto_save_script_reply`；`:443` `add_script_files`；`:473` `pet_script_structure_batch`。

接口事实：
- `writing_api.py:46` `selected_model`；`:63` `capture_request_model`；`:351` `_complete_brief`；`:374` `_write_script_raw`；`:423` `_auto_save_script_raw`；`:764` `_preparation_state`；`:1170` `reply`；`:1241` `_versioned_publisher`；`:1315` `_save_formal_script`。
- `orchestrator/writing_preparation_ledger.py:18` `PREPARATION_STAGES=('项目设定','剧本大纲','角色卡')`；`:50` `_record_confirmation_snapshots`；`:288` `_preparation_rollback`。
- `contract/script_contract.py:109` `natural_script_paths`；`:166` `natural_script_selection_path`；`:366` `resolve_script_source`；`:980` `STAGE_LOCK_REQUIREMENTS['script']`；`:985` `PRODUCTION_LOCK_DEFINITIONS`；`:1041` `stage_lock_requirements`。
- `orchestrator/stage_completion_service.py:594` `preparation_progress`；`:666` `_script_adoption_state`；`:720` `completion_evidence`（script 分支 `:736-754`，质检 `QUALITY_BLOCKING` 硬卡）。
- `domain/script_workspace_service.py:281` `adopt_natural_script`；`:626/670/769` `adoption_snapshot`/`judge_adoption`/`apply_adoption`。
- `domain/idea_chat.py:472` `_append_raw_brief`；`:488` `save_brief_creation`；`:520` `BRIEF_ATTACHMENT_NOTICE`；`:523` `receive_brief`；`:621` `initial_brief_document`；`:638` `default_brief_document`；`:389` `import_local_document`；`:364` `auto_save_reply`；`:193` `import_downloaded_documents`。
- `stage_execution_service.py:236` `adopt_natural_script`；`:246` `confirm_writing_preparation`；`:252` `unconfirm_writing_preparation`；`:264` `reply_to_writing`；`:278` `collect_writing_quality`；`:328` `idea_attachment_local_mode`；`:340` `archive_idea_attachments`；`:360` `stage_idea_attachment_paths`。
- `orchestrator/writing_unconfirm.py:20` `confirm_preparation_document`；`:107` `preparation_confirmed_stages`；`:122` `unconfirm_preparation_document`；`:189` `apply_partial_adoption`。
- `orchestrator/idea_chat_controller.py:178` `prepare_submission`；`:205` `begin_request`；`:332` `start_attachment_preparation`。
- `infra/storage_maintenance.py:65` `RECYCLE_RETENTION_DAYS`；`:315` `recycle_paths`；`infra/pet_state.py:16` `PAGE_OF`。

## 差异清单（文档 vs 代码，不改既有条目）

1. `build_script_quality_buttons`（`ui/desktop_writing_page.py:110`）仍定义「质检报告」「采风」按钮但无调用方；R2923 页脚动作栏整体删除后 `recon_button` 不再存在，`update_recon_button`/`refresh_recon_state` 为 getattr 兜底的无害死分支；`collect_recon`/`open_script_quality`/`refresh_script_workspace`/`import_script_downloads`/`auto_save_script_reply`/`add_script_files` 方法保留、页内无入口。已在 UX-S01-28 按代码现状写明。
2. S01 页未登记 `set_stage_action`（仅 S02 `_register_send_action` 与 S03 `storyboard_files.py:689` 使用），`EMPTY_SEND_STAGES` 不含 `script`：空输入点发送在剧本页为不受理 no-op（草稿保留）。已写入 UX-S01-29。
3. `_send_free` 对 `stage=='script'` 恒走 `send_message`，`send_stage_file`/`_open_flow` 的 script 分支是 `/技能名` 回落链才会用到的兜底；已写入 IF-S01-66。

## 验收

命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`（工作目录 `程序/`）。
输出：`architecture.test_stage_doc_sections 10 条`、`test_agent_doc_budget 11 条`、`test_requirement_traceability 5 条`、`test_design_coverage 8 条`，共 34 用例，0 文件有红，`ALL TESTS PASSED`，退出码 0。

## 未验证项

- `VoiceInput`/`speech_api.create_session` 的会话建立与降级分支只核到入口签名（`desktop_shared_send.py:944`、AGENTS.md 2.2 表），未逐行读 `domain/speech_api.py`。
- `recon_service.MATERIAL_SOURCES`、`skill_tools` 的 `recon.card` 注册细节未逐行核（入口 `collect_recon`、`save_request` 已核）。
- `hitl.parse_choice_reply`/`_embed_choice_card` 的选择卡渲染细节只核到调用点（`ui/desktop_idea_bubbles.py:453-454`）。
- `infra/file_index`/`ScriptListLoadController` 索引加载内部未逐行核（面板入口与视图切换已核）。
