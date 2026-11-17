# R3088 结果：T10 包化——ui/（L4 界面层）第四批 22 个模块迁移（desktop 页面族＋pet_ui mixin 族）
<!-- round-evidence: {"commit_base": "2395874c", "credential_hits": 0, "evidence_sha256": "2bfcd13479805bbd", "exit": 0, "failed": 0, "passed": 887, "round": 3088, "tests": "run_selftests.py -k desktop_asset_pages desktop_files_panel desktop_idea_attachments desktop_idea_bubbles desktop_layout desktop_media_pages desktop_page_nav desktop_page_registry desktop_pet_bridge desktop_project_pages desktop_script_pages desktop_storyboard_page desktop_writing_page pet_models_ui pet_report pet_settings_ui pet_ui_settings pet_ui_view pet_ui_voice skill_tools storyboard_files video_progress desktop_auto_flows desktop_idea_chat pet_ui data_table_boundary handoff_publication_boundary stage_command_contract stage_display_boundary storyboard_edit_boundary storyboard_final_selection_boundary subtitle_export_publication_boundary account_security app_logging app_metadata button_consistency continuity_scope delivery_scope editing_scope line_endings req_s13_anchors script_workspace_results"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`run_selftests.py -k` 定向与 `smoke_test.py --architecture` 架构门禁结果见验证记录；覆盖率基线重测结果见验证记录。
3. **欠账少了吗**：是。T10 包化 **ui/ L4 第四批**：`ui/` 实体由 81 → 103 个。L4 顶层剩余约 35 个实体继续分批；L3 仅剩 `writing_api`（拆分批）、`stage_execution_service`（扇出 50 单独一轮）、`image_agent_runner`（子进程入口永久除外）；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `ui/` 实体 | 22 个顶层 L4 模块 `git mv` 入 `ui/`：desktop 页面族 13 个（desktop_asset_pages、desktop_files_panel、desktop_idea_attachments、desktop_idea_bubbles、desktop_layout、desktop_media_pages、desktop_page_nav、desktop_pet_bridge、desktop_project_pages、desktop_script_pages、desktop_storyboard_page、desktop_writing_page、desktop_page_registry）＋pet_ui mixin 族 6 个（pet_ui_settings、pet_ui_view、pet_ui_voice、pet_settings_ui、pet_report、pet_models_ui）＋skill_tools、storyboard_files、video_progress。 |
| 别名门面 ×22 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = ui.<名>` 别名门面（R3085 教训内化：package_migrate 默认显式再导出会破坏 mock.patch 补丁面，本批直接按 domain.projects 体例写别名）。 |
| 消费方 import | 21 个生产文件改包路径导入（app.py、desktop.py、desktop_auto_flows.py、desktop_idea_chat.py、orchestrator/skill_orchestrator.py、pet_ui.py 及 ui/ 内 15 个消费方）；批内边 10 条（desktop_page_registry←5、video_progress←media_pages、skill_tools←writing_page、pet_models_ui←settings×2、pet_report←voice/skill_tools）随批同迁；AST 复扫残留 1 处逗号多导 `import …, skill_tools`（ui/desktop_writing_page.py:134）手工补 `ui.skill_tools as skill_tools`，复扫 **0 处**。 |
| 动态串 ×8 | 全部为**误报**：`storyboard_selection.py` 的 `'storyboard_files'` 系 JSON 键、`pet_ui.py`/`ui/*.py` 的 `'pet_report'` 系 `getattr(host,'pet_report')`/`host.pet_report()` 属性名——非模块引用，零改动。 |
| `__file__` 锚点 ×1 | `ui/desktop_project_pages.py` `create_practice_project` 的示例工程路径 `Path(__file__).parent/'说明'/'示例'/'雨夜修伞'` → `.parents[1]`（说明目录在程序根，入包后父目录变 ui/ 会找不到）。 |
| 日志名冻结 ×2 | `desktop_layout`、`desktop_script_pages` 的 `logging.getLogger(__name__)` → 字面量扁平名。 |
| 测试取径 ×15 文件 | 直读门面源码改 `entity_file()`：`test_data_table_boundary`（×2）、`test_handoff_publication_boundary`（×2）、`test_stage_display_boundary`（desktop_page_registry）、`test_storyboard_edit_boundary`、`test_storyboard_final_selection_boundary`、`test_subtitle_export_publication_boundary`（skill_tools）、`test_account_security`（desktop_media_pages）、`test_app_logging`（desktop_page_nav）、`test_app_metadata`（pet_ui_settings/pet_settings_ui 入 DISPLAY_SOURCES）、`test_button_consistency`（desktop_layout）、`test_continuity_scope`（×2）、`test_delivery_scope`、`test_editing_scope`、`test_req_s13_anchors`（desktop_media_pages×4 文件同款）、`test_script_workspace_results`（×2）。`_scan.DESKTOP_PARTS`/`PET_UI_PARTS`、`test_complexity_ratchet`/`test_module_size_ratchet`/`test_token_boundary`/`test_stage_display_boundary` 映射表、`test_event_bus_boundary`/`test_file_dialog_boundary`/`test_notification_boundary`/`test_platform_opening`/`test_responsive_layout_contract`/`test_startup_budget`/`test_line_endings`/`test_file_cache` 均 basename/registry_key/module_scan_files 口径，零改动。 |
| 冒烟源路径 ×6 | `smoke_test.py` `程序\storyboard_files.py`×3、`程序\skill_tools.py`、`程序\pet_models_ui.py`×2 → `程序\ui\…`（同前批先例）；`_AFFECTED_TEST_ALIASES` 扁平名映射不变。 |
| 棘轮台账 | `架构统一基数.json` 本批模块命中待架构门禁复核（R3085 已修 video_prompt_results relpath）；`_layers.py` 扁平登记名天然兼容。 |
| 基线与文档 | `architecture.md`「五批共 103 个」；`PROJECT_MAP.md` ×10 处路径改 `ui/` 前缀（storyboard_files/desktop 页面族/pet_ui mixin 描述/skill_panel_support）；覆盖率基线与 runbook §11 见验证记录。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过（源路径修复后）。
- `run_selftests.py -k <本批 22 模块＋desktop_auto_flows/desktop_idea_chat/pet_ui 消费方＋15 个触及测试文件对应关键词>`：33 文件 **958 条用例／59.6s／3 文件红**——`test_storyboard_final_selection_boundary`（本批取径修复误删 ROOT 定义，补回）、`test_data_table_boundary`（rglob 键 `ui\desktop_project_pages.py` vs 扁平期望，键改 `.as_posix()`＋期望更新为包路径）、`test_line_endings`（WRITERS 读门面，改 entity_file）；修复后三文件 **37 条全绿**，其余 30 文件首轮全绿（含全部 pet_ui#1–49 GUI 用例）。
- `smoke_test.py --architecture`：首轮 **2 红**——`test_round_number_continuous`（状态页轮次头 3086 陈旧，临时同步 3089）、`test_l4_stage_command_callers_use_registry_entrypoint`（`_L4_COMMAND_MODULES` 含 desktop_pet_bridge，`ROOT/name.py` 读门面致 registry_calls 空，改 entity_file 取径）；修复后复跑 **471/471 全绿**（195.4s）。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json` 重测写入 **696 模块／74 覆盖**（674+22，97 条目标用例全过）；`runbook.md` §11 同步（696/74/622）。
- 未跑：`--all --safe` 全量；`distribution_build --verify`（同前批口径）。

## 过程损耗（如实）

- **轮次号**：`round_claim.py next` 领得 **R3088**（3086/3087 被并行车道占用）；新建 `codex/wip-R3088` 分支叠加在 `codex/wip-R3085`（2395874c）之上承接本批。
- **门面体例**：本批起直接按 `sys.modules` 别名写门面（R3085 的 package_migrate 显式再导出回归教训内化），未再返工。
- **DESKTOP_PARTS/PET_UI_PARTS 零改动验证**：desktop_text()/pet_ui_text() 自 R3082 起走 entity_file，本批 15 个聚合部件迁移后源码聚合自动落到 ui/ 实体，架构门禁复核确认。

## 下一步（T10 后续批次）

- L4 剩余约 35 个顶层实体：account_inputs、asset_detail、asset_reference_images、production_lock_fields、white_model、ui_rounded、ui_shortcuts、ui_motion、ui_dialogs、ui_theme、skill_panel、skill_panel_import、skill_panel_support、skill_import_service、environment_check、desktop_tray、desktop_shared_send、desktop_shared_input、shot_numbering、keyframe_comfy、keyframe_import、app、desktop、pet_ui、pet_ui_support、pet_ui_stages、pet_agent、responsive_ui、cell_hover、local_video、asset_thumbs、ui_icons、ui_widgets 等——其中 desktop_tray/environment_check/keyframe_import/desktop_shared_send/skill_panel_import/skill_panel/skill_import_service/pet_ui_support/keyframe_comfy/desktop_shared_input/desktop_idea_chat 有 `__file__`/`__main__` 锚点需逐个评估；app/desktop/pet_ui/pet_agent/ui_widgets/responsive_ui 等大模块建议随拆分或专轮。
- L3 收官：`stage_execution_service`（扇出 50）单独一轮；`writing_api` 随拆分；`image_agent_runner` 永久除外。
- 门面清除轮需单独授权。
