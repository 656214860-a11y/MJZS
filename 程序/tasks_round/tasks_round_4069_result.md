# R4069 结果：首帧管理阶段文档补「接口」「交互」两节（DOC-S08）
<!-- round-evidence: {"commit_base": "5c85dd13", "credential_hits": 0, "evidence_sha256": "803413d191086df2", "exit": 0, "failed": 0, "passed": 10, "round": 4069, "tests": "run_selftests.py -k stage_doc_sections"} -->

## 开头三问

1. **本轮类型**：文档轮（任务卡 DOC-S08，《工程文档细化任务书》§4.9）。未修改任何 `.py` 文件。
2. **测试与基线**：文档轮不跑默认冒烟与全量（均未运行）；任务卡验收命令 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 已跑：共 34 条用例、0 个文件有红、实际跳过 0 条、退出码 0、输出 `ALL TESTS PASSED`。
3. **欠账**：本轮无新欠账。

## 改了什么

给 `docs/stages/S08_首帧管理.md` 末尾追加「## 接口」「## 交互」两节，原有内容未动。各小节行数：读入 10 行、写出 10 行、完成判定与交接 7 行、对外调用 4 行；页面区域 5 条（另有 1 行共用部分说明）、控件与操作 17 行、页面状态 8 行、键盘右键与拖放 4 行。状态记号合计：✅ 58 行、🟡 1 行、⬜ 1 行、❓ 0 行。

## 读过的文件清单

- `docs/process/阶段文档写法.md` 1–81
- `tests/architecture/test_stage_doc_sections.py`（六条规则与末尾 `_COMPLIANT` 样例）
- `docs/stages/S08_首帧管理.md` 1–116（追加前）、117–225（追加后复核）
- `ui/desktop_storyboard_page.py` 1–413
- `ui/desktop_media_pages.py` 100–192、370–478（`keyframe_signature` 108、`keyframe_batch_state` 123、`start_keyframe_batch` 147、`pet_frame_batch` 171、`launch_comfy` 373、`current_frame_json` 438、`delete_keyframe` 455、`restore_keyframe` 472、「尚无首帧」定位 429）
- `ui/desktop_auto_flows.py`（`poll_auto_keyframe`、` _tick_auto_keyframe`，约 439 起）
- `ui/desktop_pet_bridge.py` 104–137（`batch_blockers`、`pet_report`）
- `ui/desktop_page_nav.py` 75–149（`go`、`show`）
- `ui/cell_menu.py` 1–84（`popup_row_menu` 38、`bind_row_menu` 58）
- `ui/keyframe_import.py` 1–217（`pending_tasks` 13、`publish_frame_reference` 43、`register` 61、`launch` 127、`resume` 200、`watch_list` 207）
- `ui/keyframe_comfy.py` 1–253 及 585–860 抽查（`saved_settings` 41、`write_settings` 57、`seedream_cost_preview` 109、`run_seedream` 130、`auto_batch` 221、`show` 253、`launch_agent` 777、`start` 797）
- `ui/pet_ui_stages.py` 60–149、820–959（`completion_evidence` 66、`_complete_if_verified` 69、`report_done` 119、`should_auto_run` 823、`firstframe_batch` 938）
- `responsive_ui.py` 80–174（`bind_row_toggle` 86、`bind_space_toggle` 97、`work_rows` 151、`work_hint` 166）
- `desktop.py` 532–576（`button` 537、`safe` 557）、803–814（`note` 807）
- `orchestrator/stage_flow.py` 55–79（`DEPENDS`、`PAID_STAGES`）、256–340（`blockers`、`summary_lines`）
- `orchestrator/stage_models.py` 155–284（`plan` 161、`plan_window` 236、`open_config` 255）
- `orchestrator/stage_parallel.py`（`CONFIG['keyframe']`、`GATES`、SG-03 `batches_ready`、SG-04 `frames_ready`、`_shot_frame_problem`，约 780–870）
- `orchestrator/stage_completion_service.py` 730–859（`completion_evidence`、`emit_verified_completion`、`publish_stage_manifest`）
- `orchestrator/stage_handler_registry.py`（`start`、制作锁检查，约 20–115）
- `orchestrator/stage_write_preparation_service.py` 1–129（`prepare_stage_write` 21、`prepare_legacy_stage_path` 113）
- `orchestrator/stage_config.py` 225–264（`workflow_lock` 231）
- `orchestrator/storyboard_selection.py` 95–169（`current_source`）
- `orchestrator/keyframe_model_service.py` 1–45（`current_model` 27）
- `orchestrator/keyframe_page_controller.py` 1–80
- `orchestrator/media_page_controller.py` 1–100（`keyframe_batch_verdict` 34）
- `orchestrator/page_navigation_controller.py` 125–136（`decide`）
- `domain/keyframe_batch.py` 1–282（`frame_prompt`、`MODE_*`、`STATE_*`、`candidates`、`image_prompt`）
- `domain/keyframe_evidence.py` 1–166（`image_facts`、`_check_dimensions`、`make_evidence`、`source_evidence`、`frame_problem`）
- `domain/keyframe_lifecycle_service.py` 1–176（`delete_keyframe` 47、`restore_keyframe` 84、`replace_keyframe` 127、`KEYFRAME_REPLACED` 发出 174）
- `domain/domain_events.py` 22（`KEYFRAME_REPLACED`）；`contract/pet_bus.py` 60（事件登记）
- `contract/stage_path_service.py` 1–94（`write_dir`、`read_dirs`、`LEGACY_NUMBERED`）
- `contract/frame_checks.py` 1–98
- `contract/storyboard_paths.py` 1–60（`media_root` 21）
- `contract/script_contract.py` 955–1044（`STAGE_LOCK_REQUIREMENTS` 964、`stage_lock_requirements` 1026）
- `contract/file_naming.py`（`generate_existing`，经 `ui/keyframe_import.py:80`）
- `agent/shot_assets.py` 55–99（`summary` 61）
- `agent/core.py`（`read`／`save`／`save_bytes_new`，经 `ui/keyframe_import.py:85`）
- `infra/seedream_api.py` 85–154（`load_profile` 97、`request_image` 120、`Rejected`／`Uncertain` 116–117）
- `infra/native_apps.py` 18–57（`open_comfy` 24、`comfy_server_pids` 29、128 `wait_comfy` 定义行）
- `infra/comfy_runtime.py` 18–35（`open_comfy`、`wait_comfy`）
- `image_agent_runner.py` 1–128（`task_instruction` 8、`execute` 43、首帧批次分支 95–120）
- `batch_frames_tool/batch_frames.py` 1–60（`load_assets` 17、`Client` 36、`run`）
- `local_video.py` 230–309（`auto_plan` 282、「尚无首帧」305）
- `docs/specs/08_对话式交互与输出排版.md`、`docs/specs/09_资产数据生命周期.md`（确认存在，用于相对链接）
- `tasks_round/专题二资产数据盘点报告.md`（只用于找代码位置，未凭其标 ✅）

## 控件数对照

构建代码（`_FirstFramePage.build`／`_build_state_and_table`／`StoryboardPageMixin.storyboard`）创建的可操作控件共 13 类：8 个按钮（空项目「去第03步」、主按钮「手动制作首帧」、选中镜头行 6 个次按钮）、1 个「选中镜头」下拉框、1 个 `#0` 勾选列（含表头全选）、2 个可点链接格（「图片文件(点击查看)」「首帧图片提示词(点击查看)」）、1 层缩略图盖图（`CellImages`）。

「控件与操作」表共 17 行。两数不等，逐条说明：

- `#0` 勾选列按「表头全选」（UX-S08-10）与「行勾选」（UX-S08-11）两处操作记 2 行；
- 缩略图盖图有「单击打开图片」（并入 UX-S08-12）与「悬停放大」（UX-S08-14）两种操作，悬停单独记 1 行；
- `bind_row_toggle`（UX-S08-15）与行高亮选择（UX-S08-16）是表格上的鼠标绑定，不新增控件，记 2 行；
- UX-S08-17「过程与回话区」是未实现目标行，代码中没有对应控件；
- `pet.auto_variable('auto_first_frame_var')` 创建的三虎自动勾选挂在三虎面板（共用部分），不计入本页控件；`watch_list` 文件监听、`<<TreeviewSelect>>`/`<<ComboboxSelected>>` 绑定不是用户可操作控件，均不单列。

## 差异清单

- REQ-S08-24：文档写「首帧图写入 `08首帧管理/` 下阶段目录」；代码把首帧 PNG 写到 `<分镜媒体目录>/frames/`（`ui/keyframe_import.py:77-85` 经 `file_naming.generate_existing`＋`save_bytes_new`，`domain/keyframe_lifecycle_service.py:127` `replace_keyframe` 经 `publish_stage_bytes`）；`08首帧管理/output/` 只落 `frames.json` 清单（`orchestrator/stage_completion_service.py:828-852` `publish_stage_manifest`）。
- REQ-S08-18：文档写「首帧模型以阶段配置（`stage_config` 的 `keyframe.model`）为唯一来源」；代码另有旧项目回退——`orchestrator/keyframe_model_service.current_model` 在阶段配置缺失时读 `ui_settings.json` 的 `frame_production`、再回退本机模型（`orchestrator/keyframe_model_service.py:27-45`；`ui/keyframe_comfy.py:390-392`）。
- 「模块分工」表：`keyframe_comfy`、`keyframe_import` 列在 L3；实现文件在 `ui/` 包（L4）——`ui/keyframe_comfy.py:253`（`show`）、`ui/keyframe_import.py:61`（`register`）；根级同名文件为转发壳，表中 L3 只能对应壳。
- 总控复核：已抽查 7 行已实现条目，代码位置与界面文字相符；上面列出的差异由总控登记，另行处理，不在本轮改。

## 待裁决清单

无。

## 没做的

任务卡验收命令已由本卡（B-DOC-S08-FIN）执行：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`，共 34 条用例、0 个文件有红、退出码 0、输出 `ALL TESTS PASSED`；已领号 R4069；由本卡提交。除上述收尾动作外没有其他没做的事项。
