# R4083 结果：视频生成阶段文档补「接口」「交互」两节（DOC-S10）
<!-- round-evidence: {"commit_base": "07443810", "credential_hits": 0, "evidence_sha256": "73675d4e783e78f6", "exit": 0, "failed": 0, "passed": 10, "round": 4083, "tests": "run_selftests.py -k stage_doc_sections"} -->

## 开头三问

1. **本轮类型**：文档轮（任务卡 DOC-S10，《工程文档细化任务书》§4.9）。未修改任何 `.py` 文件。
2. **测试与基线**：文档轮不跑默认冒烟与全量（均未运行）；任务卡验收命令 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 已跑：4 个匹配测试文件（`architecture.test_stage_doc_sections` 10 条、`architecture.test_agent_doc_budget` 11 条、`architecture.test_requirement_traceability` 5 条、`architecture.test_design_coverage` 8 条）、共 34 条用例、0 个文件有红、实际跳过 0 条、退出码 0、输出 `ALL TESTS PASSED`，一轮通过（此前曾在默认 bash 会话误发同一条命令一次，中文相对路径被转义、退出码 127 未启动，随后在 PowerShell 会话原样执行成功）。
3. **欠账**：本轮无新欠账。

## 改了什么

给 `docs/stages/S10_视频生成.md` 末尾追加「## 接口」「## 交互」两节，原有内容未动（`git diff --numstat` 新增 173 行、删除 0 行）。各小节行数：读入 19 行、写出 15 行、完成判定与交接 13 行、对外调用 7 行；页面区域 10 条（含 1 条未实现目标「过程与回话区」，另有 1 行共用部分说明）、控件与操作 42 行、页面状态 13 行、键盘右键与拖放 10 行。状态记号合计：✅ 116 行、🟡 2 行（IF-S10-34、IF-S10-52）、⬜ 1 行（UX-S10-42）、❓ 0 行。

## 读过的文件清单

- `docs/process/阶段文档写法.md`、`tests/architecture/test_stage_doc_sections.py`（六条规则与末尾 `_COMPLIANT` 样例）
- `docs/stages/S10_视频生成.md` 1–121（追加前全文）
- `docs/stages/S08_首帧管理.md` 130–225、`docs/stages/S09_白模预演.md`（只看写法与详略，未抄事实）
- `docs/specs/08_对话式交互与输出排版.md`、`docs/specs/09_资产数据生命周期.md`（确认存在，用于相对链接）
- `tasks_round/专题二资产数据盘点报告.md`（F18/F22–F25/F30 用于定位代码，✅ 行均另有本轮代码证据）
- `ui/desktop_media_pages.py` 1–31、400–716（`focus_missing_frame`、`current_frame_json`、`video_home`、`refresh_video_workspace`、`set_video_workspace`、`videos`、`prepare_video_prompt`、`VIDEO_PROMPT_FLOW`）
- `app.py` 40–60、64–314、575–874、1040–1392、1478–1487（`pending_checked_shots`、`play_ready`、`work_targets`、`App.__init__` 及全部 `_build_*` 方法、`select`、`cell_actions`、`shot_menu`、`delete_video_shot`、`delete_checked_shots`、`refresh`、`update_progress`、`auto_poll`、`ensure_frame`、`frame`、`play`、`versions`、`save_options`、`save_prompt`、`flush_prompt`、`review`、`import_prompt`、`start_prompt_skill`、`make_prompt`、`confirm_submit`、`auto_submit_scan`、`generate`、`generate_checked`、`attach`、`settings`、`open_assembled`、`run`、`tick`）
- `ui/video_navigation.py` 1–134、`ui/video_progress.py` 1–153、`ui/shared_video_controls.py` 1–20、`ui/ui_stage_popups.py` 100–168
- `ui/pet_ui.py` 60–119（`should_auto_run`）、`ui/pet_ui_stages.py` 55–174、290–499（`_completion_evidence`、`_complete_if_verified`、`start_stage`、`paid` 分支）
- `ui/desktop_idea_chat.py`（grep 定位 `_FlowAgentLaunch`）、`ui/desktop_direct_dispatch.py` 19–23（grep 定位 `video_prompt` 直连分流）、`ui/desktop_video_prompt_direct.py`（前轮已读）
- `ui/asset_detail.py` 640–687（`asset_impact_note`、`show_roster`）、`ui/storyboard_files.py` 955–994（`adopt_selected` 用 `adoption_impact`）
- `ui/video_prompt_results.py`（前轮已读）、`ui/cloud_video.py`、`local_video.py`（前轮已读）
- `orchestrator/engine.py`（前轮已读全文；本轮 grep 复核 `task_folder`/`submit`/`poll`/`review`/`pin_version`/`attach`/`auto_edit_ready`/`publish_manifest`/`cloud_index`/`remaining`/`used`/`record_video_usage`/`adopted_edit_version`/`edit_ready_rows`/`episode_file_of` 行位）
- `orchestrator/stage_flow.py` 55–294、`orchestrator/stage_parallel.py` 45–224、515–574、860–959、`orchestrator/stage_completion_service.py` 695–834、`orchestrator/stage_handler_registry.py` 1–153、`orchestrator/stage_models.py` 150–379、`orchestrator/stage_handoff_gateways.py` 200–259、`orchestrator/page_navigation_controller.py`（grep 定位 74–151）、`orchestrator/video_prompt_direct_api.py`（前轮已读）
- `domain/video_task_state.py`、`domain/video_lifecycle_service.py`、`domain/cloud_video_service.py`、`domain/video_source_evidence.py`（前轮已读）
- `domain/asset_plan.py` 140–339（`asset_impact`、`_adopted_storyboard_shots`、`plan_file`、`update_fields`）、`domain/storyboard_catalog_service.py` 210–359（`_generated_video_shots`、`adoption_impact`、`_shot_rows`）
- `agent/wan.py`、`agent/volcengine.py`、`agent/shot_assets.py`（前轮已读）
- `contract/script_contract.py` 964–1037（grep 定位）、`contract/stage_layout.py` 55/76/151/402（grep 定位）、`contract/stage_path_service.py` 12–94、`contract/shot_selection.py` 3–35（`bind_shot_checks` 的 `<space>` 绑定）
- `infra/project_settings.py` 11–80（`auto_review`）、`infra/request_ledger.py`（grep 定位 `RequestLedger` 157、`authorize_units` 649、`settle_units` 710、`record_request` 819、`preview_text` 522）

## 控件数对照

构建代码创建的可操作控件共 36 个（本地工作台口径）：落地页 2 个按钮（「进入本地生成」「进入线上生成」）＋云端早退分支 1 个按钮（「配置线上视频 API」，代码有两处同名调用点）＋「手动制作：视频生成」确认窗 3 个按钮（「修改配置」「直接执行」「取消」）＋工作台 30 个（「返回生成方式」；共享行「刷新镜头」「刷新白模」「查看首帧」「启动 H3 / ComfyUI」；镜头表（含表头与逐行勾选、白模勾选按 1 类计）；「生成声音 / 音轨」勾选框；提示词动作行 6 按钮；提示词编辑框；页脚第一行「手动制作视频」「播放视频」「查看全部版本」「本地设置」；页脚第二行 7 按钮＋「验收备注：」输入框；「打开剪辑成片目录」「清空日志」）。云端工作台比本地少 3 个（无「启动 H3 / ComfyUI」「本地设置」「生成声音 / 音轨」），共 33 个。

「控件与操作」表共 42 行。两数不等，逐条说明：

- 表头勾选框（UX-S10-09）、行勾选框（UX-S10-10）、「选择资产」格（UX-S10-11）、「首帧」格（UX-S10-12）、缩略图悬停（UX-S10-13）、「白模 · 上传」勾选框（UX-S10-14）、行选择（UX-S10-15）是同一个镜头表与其覆盖层上的 7 处操作面，控件侧按镜头表 1 个＋逐行勾选类 1 个计；
- 「动态日志」框（UX-S10-41）是只读显示区，不算可操作控件，表中记 1 行；
- 「打开视频目录」（UX-S10-35）与「查看全部版本」（UX-S10-29）是两颗不同按钮同走 `App.versions`，各记 1 行；
- 确认窗三按钮（UX-S10-25～27）计入 36 个控件，表中亦各 1 行；
- UX-S10-42「过程与回话区」是未实现目标行，代码中没有对应控件；
- 空格、Ctrl+A、Esc、右键各菜单记入「键盘、右键与拖放」节（UX-S10-80～88），不在控件数里重复计。

## 差异清单

- REQ/非目标表述与代码行为存在口径差异：S10 文档「非目标（明确不做）」写「不在无人值守下提交云端付费视频」、REQ-S10-12 写「无人值守自动补视频只支持本地后端，云端按次计费，必须手动提交」；但 `app.App.auto_submit_scan`（`app.py` 1244–1266）在云端工作集（非 `LocalStudio` 且 `live_enabled`）经 `pet_ui.should_auto_run(...,'auto_submit')` 开关自动提交未提交过的镜头，`confirm_submit`（`app.py` 1235–1240）在该开关下跳过确认框并按预算闸提交。即代码存在受开关与预算约束的云端自动提交通道，与「云端必须手动提交／不做无人值守云端提交」的文档表述不一致（按卡面要求不改已有文档行，如实记录）。
- DES-S10-50 写「分流点唯一在 `desktop_idea_chat._FlowAgentLaunch.build()`」：分流条件（`stage=='video_prompt'` 且带 `direct` 且非 `intake_only`）实际位于 `ui/desktop_direct_dispatch.py` 19–23，由 `_FlowAgentLaunch.build()` 经 `desktop_idea_chat.py:750` 的 `from ui.desktop_direct_dispatch import dispatch` 调用；链路单一但字面判断位置在更下一层，文档表述可视为同一入口的概称，未改原文。

代码侧观察（不改代码，照实记录）：

- `app.py` 324、368 行的 `self.auto_submit`、`self.auto_review` 两个 `BooleanVar` 在构建代码中未创建对应勾选框（`_build_video_actions` 只建变量）；`options()` 遍历的 Checkbutton 只有「生成声音 / 音轨」一颗。自动提交／自动验收的实际开关走三虎变量与项目设置（`should_auto_run`、`project_settings.auto_review`），这两个变量疑为兼容占位。
- `desktop_media_pages.py` 649 行按 `cloud_provider=='openai'` 显示「原视频服务商已移除」的早退分支仍在，服务商表（`domain.cloud_video_service`）里已无 openai 项，属旧会话兼容路径。

## 待裁决清单

无。

## 没做的

- 默认冒烟与全量回归未运行（文档轮不跑）；任务卡验收命令已跑一轮通过。
- 未合入、未 push。
- 「设计」节条目引用到、但本轮没有逐行读的代码：`orchestrator/workflow_settings.py`（`FLOWS`/`current` 经调用点确认）、`infra/model_pool.py`（`named_key`/`save_named_key` 经 `cloud_video_service` 调用点确认）、`agent/media.py`（`check` 经 `publish_downloaded_video` 调用点确认）、`agent/prompt_optimizer.py`（`start`/`settings` 经 `app.py` 调用点确认）、`ui/white_model.py`（`shot_directory`/`read_record` 经 `app.py` 调用点确认）、`domain/previs_routing.py`（`classify`/`decisions_for`/`ready` 经 `stage_parallel.previs_ready` 调用点确认）、`infra/pet_state.py`（`Machine` 经 `stage_flow.state_of` 调用点确认）、`contract/pet_bus.py`（`STAGE_NAMES`/`stage_label`/`stage_step` 经调用点确认）、`contract/storyboard_paths.py`（`media_root` 经调用点确认）、`stage_execution_service.py`（`publish_video_prompt`/`import_video_prompt`/`save_stage_video_options`/`save_stage_white_model_upload`/`mark_stage_video_deleted`/`publish_cloud_video_workspace_preference`/`publish_cloud_video_studio_config` 经各调用点确认，未逐行读实现）、`infra/pet_llm.py`（`RequestLedger` 再导出经 `app.py:1231` 调用点确认）、`ui_plugin_registry`、`responsive_ui`（`DataTable`/`CheckboxColumn`/`FlowBar`/`QuietVar`/`bind_shot_checks` 之外的实现未逐行读）、`desktop.py`（`safe`/`show`/`async_` 经调用点确认）。
- 其他没做的事：无测试新增（文档轮）；状态页轮次头与证据文件由提交工具按流程处理。
