# R4074 结果：白模预演阶段文档补「接口」「交互」两节（DOC-S09）
<!-- round-evidence: {"commit_base": "8e21e608", "credential_hits": 0, "evidence_sha256": "a33ac0f6d0145a11", "exit": 0, "failed": 0, "passed": 10, "round": 4074, "tests": "run_selftests.py -k stage_doc_sections"} -->

## 开头三问

1. **本轮类型**：文档轮（任务卡 DOC-S09，《工程文档细化任务书》§4.9）。未修改任何 `.py` 文件。
2. **测试与基线**：文档轮不跑默认冒烟与全量（均未运行）；任务卡验收命令 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 已跑：4 个匹配测试文件、共 34 条用例、0 个文件有红、实际跳过 0 条、退出码 0、输出 `ALL TESTS PASSED`，一轮通过（此前曾在默认 bash 会话误发同一条命令一次，路径被转义、127 未启动，随后在 PowerShell 会话原样执行成功）。
3. **欠账**：本轮无新欠账。

## 改了什么

给 `docs/stages/S09_白模预演.md` 末尾追加「## 接口」「## 交互」两节，原有内容未动（`git diff --numstat` 新增 152 行、删除 0 行）。各小节行数：读入 19 行、写出 18 行、完成判定与交接 12 行、对外调用 7 行；页面区域 12 条（含 1 条未实现目标「过程与回话区」，另有 1 行共用部分说明）、控件与操作 24 行、页面状态 11 行、键盘右键与拖放 5 行。状态记号合计：✅ 95 行、🟡 0 行、⬜ 1 行、❓ 0 行。

## 读过的文件清单

- `docs/process/阶段文档写法.md` 1–95
- `tests/architecture/test_stage_doc_sections.py`（六条规则与末尾 `_COMPLIANT` 样例）
- `docs/stages/S09_白模预演.md` 1–114（追加前）、115–266（追加后复核）
- `docs/stages/S08_首帧管理.md`（只看写法与详略，未抄事实）
- `ui/desktop_media_pages.py` 430–450（`current_frame_json`、`_storyboard_source`）、560–566（`previs`）
- `ui/local_previs.py` 1–380（`online_window`、`_LocalPrevisWindow` 全部方法、模块级 `previs_engine` 行）
- `ui/white_model.py` 1–120（`TOOLS`、`import_media`、`choose_previs`／`open_previs`）
- `ui/white_model_ref.py` 1–80（`SUPPORT`、`descriptor`、`entries`、`prompt_line`）
- `ui/desktop_page_nav.py` 140–170（`blocked` 文案、`project_home` 状态段）
- `ui/desktop_auto_flows.py` 439–540（`poll_auto_previs`、`_tick_auto_previs`、签名与退避）
- `ui/ui_stage_popups.py` 100–160（`_show_manual_plan` 三按钮与 Esc/关窗绑定）
- `orchestrator/previs_automation.py` 1–260（`require_local_agent`、`start`、`worker`、`verify`、`persist`、`announce`、`force_stop`）
- `orchestrator/previs_monitor.py` 1–130（`start`、`render`、`rows`、`progress_of`、`NOTE`）
- `orchestrator/previs_batch_service.py` 1–140（`prepare_batch`）
- `orchestrator/stage_previs_gateways.py` 1–120（L3 门面）
- `orchestrator/white_model_persistence_controller.py` 1–18
- `orchestrator/page_navigation_controller.py` 60–100（`needs_adopted_storyboard`、`decide`）
- `orchestrator/storyboard_selection.py` 95–170（`current_source`、`adopted`、`focus`）
- `orchestrator/stage_flow.py` 30–80（`DEPENDS`、执行中标签）、256–345（`blockers`、`blocked_text`）
- `orchestrator/stage_parallel.py`（`CONFIG['previs']`、`GATES`、SG-04 `frames_ready`、SG-05 `previs_ready`、`_adopted`、`blocked_stages`，约 780–920）
- `orchestrator/stage_models.py` 155–290（`manual_command`、`plan`、`plan_window`、`open_config`、`before_manual`）
- `orchestrator/stage_completion_service.py` 730–860（`checks['previs']`、`emit_verified_completion`、`publish_stage_manifest`）
- `orchestrator/stage_handler_registry.py` 20–120（`start`、`_workflow_lock_error`）
- `orchestrator/stage_handoff_gateways.py` 1–60（`save_stage_white_model_upload` 33–38）
- `orchestrator/workflow_settings.py`（`current` 签名，经 `previs_automation.start`／`previs_batch_service.prepare_batch` 调用点）
- `orchestrator/workflow_engines.py`（`run_background`／`terminate`，经 `previs_automation` 调用点）
- `domain/previs_routing.py` 1–220（`LEVELS`、`classify`、`entries`、`overrides_file`、`set_override`、`decisions_for`、`partition`、`ready`、`dispatch`、`previs_automatic_candidates`／`automatic_signature`／`previs_automatic_engine`）
- `domain/white_model_service.py`（`read_record`、`shot_directory`、`project_identity`、`episode_identity`、`_episode_candidates`、`evidence_state`、`project_copy_ready`、`sync_project_copy`、`import_previs_media`、`write_record`、`find_blender`、`blender_candidates`、`blender_version`、`configured_workspace`、`settings_path`、`read_settings`、`diagnose`／`diagnose_text`、`_migrate_legacy_directories`、`legacy_base`／`legacy_workspaces`、`project_index_path`／`read_project_index`、`_publish_identity`）
- `domain/previs_progress_service.py` 1–80（`publish`、`status_value`、`install_blender_progress`）
- `stage_execution_service.py` 540–570（`record_previs_evidence`、`sync_previs_copy`）、820–840（白模勾选持久化段），及 `save_stage_previs_override`、`white_model_shot_directory`、`previs_records_directory`、`migrate_white_model_directories`、`save_stage_white_model_upload` 转发点
- `app.py` 590–640（「白模 · 上传」勾选列、`set_white_upload`）
- `contract/pet_bus.py`（`STAGES`、`PAGE`、事件登记）
- `contract/stage_path_service.py` 1–100（`LEGACY_NUMBERED`、`write_dir`、`read_dirs`、`read_file`）
- `contract/script_contract.py` 955–1050（`STAGE_LOCK_REQUIREMENTS['previs']`、`stage_lock_requirements`）
- `contract/shot_selection.py`（`bind_shot_checks` 的 space／click 绑定）
- `contract/platform_tools.py`（`open_path`）
- `infra/pet_state.py`（`PAGE_OF`）
- `infra/native_apps.py`（`open_blender`）
- `infra/file_cache.py`（`read_json`）
- `ui/ui_dialogs.py`（`FileDialog.open_file`）
- `desktop.py` 532–576（`button`、`safe`）、803–814（`note`）
- `responsive_ui.py`（`DataTable`、`CheckboxColumn`、`FlowBar`、`DescriptionBlock`、`ProgressLabel` 用法定位）
- `docs/specs/08_对话式交互与输出排版.md`、`docs/specs/09_资产数据生命周期.md`（确认存在，用于相对链接）

## 控件数对照

构建代码创建的可操作控件共 21 个：主页 10 个按钮（「白模环境检查」「去设置」「手动制作白模」「强制停止制作」「线上白模入口」「播放视频」「打开工程调整」「当前白模目录」「制作记录」「进入视频生成」）＋1 个复杂度下拉框＋1 个镜头表（勾选列与行选择）；「线上白模 · 中等动作」窗 3 个按钮＋1 个镜头下拉框＋1 个任务说明文本框；「手动制作：白模预演」确认窗 3 个按钮；空项目引导页 1 个按钮（「去第03步」）。

「控件与操作」表共 24 行。两数不等，逐条说明：

- `#0` 勾选列按「表头全选」（UX-S09-04）与「行勾选」（UX-S09-05）两处操作记 2 行；
- 行高亮选择（UX-S09-06）是 `<<TreeviewSelect>>` 绑定，不新增控件，记 1 行；
- UX-S09-24「过程与回话区」是未实现目标行，代码中没有对应控件；
- 空格、单击、Esc、右键等键鼠绑定记入键盘节（UX-S09-80～84），不新增控件；`bind_shot_checks` 的 tree/cell 绑定、750 ms 自刷是程序行为，不单列。

## 差异清单

- 无：本轮抽核的「设计」节事实（`previs` 依赖 `keyframe`、SG-04/SG-05、`stage_parallel.CONFIG['previs']` 并行口径、三项制作锁只读、`09白模预演` 新写旧读兼容 `08白模预演`）与代码一致，未发现已有文档条目与代码对不上的地方。

代码侧观察（不改代码，照实记录）：

- `ui/local_previs.py` 模块级 `previs_engine = stage_execution_service.previs_engine` 赋值后，本文件未再读取该名字，疑为遗留。
- `ui/white_model.py` 的 `choose_previs`／`open_previs` 未找到生产调用方（本页线上窗只调用 `import_media`）；如实际为其他页面入口，以调用方为准。

## 待裁决清单

无。

## 没做的

- 默认冒烟与全量回归未运行（文档轮不跑）；任务卡验收命令已跑一轮通过。
- 未合入、未 push。
- 「设计」节条目引用到、但本轮没有逐行读的代码：`orchestrator/workflow_engines.py`（只经 `previs_automation` 调用点确认 `run_background`／`terminate` 签名与语义）、`orchestrator/workflow_settings.py`（只确认 `current` 签名与返回键）、`agent/shot_assets.py`（`assets` 经 `prepare_batch` 调用点确认）、`contract/storyboard_paths.py`（`media_root` 经调用点确认）、`domain/video_lifecycle_service.py`（`save_white_model_upload` 经 `stage_handoff_gateways` 转发确认）、`infra/integrations.py`（`tool_path('ffprobe')` 经 `previs_automation.verify` 调用点确认）、`ui_plugin_registry` 与 `empty_stage_guide`／`storyboard_missing_text` 实现（经 `desktop_media_pages.previs` 调用点确认）。
- 其他没做的事：无测试新增（文档轮）；状态页轮次头与证据文件由提交工具按流程处理。
