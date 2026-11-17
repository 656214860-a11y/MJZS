# R3082 结果：T10 包化——ui/（L4 界面层）第二批 20 个低扇出模块迁移
<!-- round-evidence: {"commit_base": "3008566c", "credential_hits": 0, "evidence_sha256": "848a9441d6ea21a2", "exit": 0, "failed": 0, "passed": 438, "round": 3082, "tests": "run_selftests.py -k asset_prompt_check task_center_ui asset_reference_import background_characters reference_wall cloud_video local_previs asset_batch native_assets asset_reference_prompts desktop_image_direct desktop_direct_dispatch desktop_storyboard_direct desktop_video_prompt_direct desktop_audio_direct desktop_file_card desktop_idea_deferred desktop_login_gate desktop_idea_send_gate desktop_idea_menus task_center reference_images previs login_gate idea_chat idea_menus file_card direct_dispatch ui_batch8 static_names button_consistency"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`run_selftests.py -k` 定向与 `smoke_test.py --architecture` 架构门禁结果见验证记录；覆盖率基线重测 650 模块／74 覆盖。
3. **欠账少了吗**：是。T10 包化 **ui/ L4 第二批**：`ui/` 实体由 37 → 57 个。L4 顶层剩余约 81 个实体继续分批；L3 仅剩 `writing_api`（拆分批）、`stage_execution_service`（扇出 50 单独一轮）、`image_agent_runner`（子进程入口永久除外）；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `ui/` 实体 | 20 个低扇出（入度 0–1）顶层 L4 模块 `git mv` 入 `ui/`：asset_prompt_check_dialog、task_center_ui、asset_reference_import、background_characters、reference_wall、cloud_video、local_previs、asset_batch、native_assets、asset_reference_prompts_dialog、desktop_image_direct、desktop_direct_dispatch、desktop_storyboard_direct、desktop_video_prompt_direct、desktop_audio_direct、desktop_file_card、desktop_idea_deferred、desktop_login_gate、desktop_idea_send_gate、desktop_idea_menus。 |
| 别名门面 ×20 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = ui.<名>` 别名门面；20/20 `import <扁平名> is import ui.<名>` 实体同一校验全过。 |
| 消费方 import | 5 个生产文件改包路径导入（desktop.py、desktop_asset_pages.py、desktop_files_panel.py、desktop_idea_chat.py、ui/desktop_direct_dispatch.py 批内 4 条懒加载边）；AST 复扫残留 **0 处**。其余模块入度 0–1，经 `ui_plugin_registry.module()` 扁平键动态装配（门面解析，注册表键表不动）。逻辑零改动，仅 import 行。 |
| `__file__` 锚点 ×2 | `ui/cloud_video.py` `saved_provider_key` 的 `module_file` 实参改 `parents[1]/<自身名>`——下游取 `.parent/'private/.env'`，入包后父目录变 `ui/` 会丢真实凭据目录，锚回程序根（`test_cloud_video` 的 `patch('cloud_video.__file__')` 夹具仍落在临时目录内，语义不变）；`ui/asset_batch.py` `Path(__file__).with_name('flux2_klein_asset_text_api.json')` 改 `parents[1]/文件名`——JSON 数据文件留顶层，锚回程序根。 |
| 测试取径 ×19 | 直读门面源码改 `entity_file()`：`test_asset_batch_settings_boundary`、`test_busy_state_boundary`（filename 循环）、`test_cloud_video_settings_boundary`、`test_data_table_boundary`（×3）、`test_previs_routing_publication_boundary`、`test_task_center`（×3）、`test_reference_images`、`test_ui_edges_guards`（local_previs 直读）、`test_asset_batch_settings_callers`（parents[1] 直读＋编译抽取，改 entity_file 后 4 分支恢复命中）、`test_local_previs_json_boundary`、`test_responsive_layout_contract`（PAGES entity_file 化，含 `agent/` 子目录兜底写法见 notification）、`test_file_dialog_boundary`、`test_notification_boundary`（LEGACY 表 entity_file 化，`agent/prompt_optimizer.py` 子目录条目走 `ROOT/` 直读兜底）、`test_platform_opening`（MIGRATED 表）；`test_static_names.modules()` 扫描面补 `PACKAGE_NAMES` 包实体（否则 ui/ 实体逃逸未定义名检查）；`test_button_consistency` DIALOG_FILES、`test_ui_batch8_video_ui_tokens` TARGETS 同改 entity_file。 |
| `_scan` 基建修复 ×2 | **`desktop_text()`/`pet_ui_text()` 改走 `entity_file()`**——此前 `(ROOT/name)` 直读：本批 `desktop_idea_menus.py` 与 R3059 已迁的 `pet_ui_popup.py` 自迁移起即被门面顶替，相关源码行为断言静默落空（本轮架构门禁在修复后仍 471/471，证明被遮蔽断言的真实内容本就满足）；`test_silent_exception_ratchet.test_swallowed_helper_is_used_widely` 计数面由 `PROGRAM.glob('*.py')` 改 `_scanned_files()`（与本文件其余检查同扫描面，包实体不再漏计）。 |
| 棘轮台账 | `架构统一基数.json` 本批 20 模块精确名零命中（存量 `asset_batch_*` 均为已迁 L2 服务模块，非本批 UI 模块）；`_layers.py` 扁平登记名天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **650 模块／74 覆盖**（630+20，97 条目标用例全过）；`runbook.md` §11 同步（650/74/576）；`architecture.md` ui 目录树「两批共 37 个」→「三批共 57 个」；`distribution_manifest.md` `程序/ui/**` glob 已覆盖；`PROJECT_MAP.md` `desktop_idea_menus`/`local_previs`/`cloud_video` 路径改 `ui/` 前缀。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过。
- `run_selftests.py -k <本批模块关键词＋task_center/reference_images/previs/login_gate/idea_chat/idea_menus/file_card/direct_dispatch/ui_batch8/static_names/button_consistency>`：首轮 **418 条用例／528.7s／2 文件红**——`architecture.test_local_previs_json_boundary`（直读门面）与 `test_asset_batch_settings_callers`（parents[1] 直读致 0 分支，实为确定性门面误读非并发抖动）；修复后该两文件＋`test_static_names`/`test_button_consistency`/`test_ui_batch8` 补跑 **20+3 条全绿**，其余首轮全绿。
- `smoke_test.py --architecture`：首轮 **3 红**（local_previs_json_boundary、responsive_layout_contract 的 asset_batch.py、silent_exception_ratchet 计数 99<100）——全部门面误读/扫描面漏包所致；修复后二轮 **471/471 全绿（200.4s）**；三处补充取径（file_dialog/notification/platform_opening）单独复测 11 条绿。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入（97 条目标用例全通过）。
- 未跑：`--all --safe` 全量；`distribution_build --verify`（同前批口径）。

## 过程损耗（如实）

- **轮次号**：`round_claim.py next` 领得 **R3082**（3060–3081 被并行车道占用）；新建 `codex/wip-R3082` 分支叠加在 `codex/wip-R3059`（3008566c）之上承接本批。
- **R3059 提交损耗（前轮结转）**：首次 `dev.py commit` 因 `--tests` nargs='*' 吞掉尾随文件参数、证据跑混入文件路径关键词致 1 文件红被拒；改为先 `git add -A` 暂存全量（除 `project_status.md`——仅 master 可提交）、commit 只传 `-m`＋`--tests` 关键词后通过（commit `3008566c`，74 文件）。本轮沿用「先暂存、后只传关键词」口径。
- **`__file__` 锚点两处真实语义修复**：非纯机械搬家——`cloud_video` 的 `private/.env` 凭据回退与 `asset_batch` 的 workflow JSON 路径若不改锚会在 `ui/` 下找不到文件；均已按 `.parents[1]` 锚回程序根并复核测试夹具兼容。
- **`desktop_text()`/`pet_ui_text()` 门面遮蔽（系统性发现）**：`_scan.py` 两个 Desktop/Pet 合并源码入口自始直读 `ROOT/name`，未走 `entity_file`——R3059 迁 `pet_ui_popup`、本批迁 `desktop_idea_menus` 后，对应源码行为断言实际在读 3 行门面（静默弱化，非报错）。已修为 entity_file 取径；**教训：凡「合并多文件源码」的测试基建都必须逐名 entity_file 化，光修单层 `parse(ROOT/x)` 不够**。`test_static_names` 扫描面同样漏包实体，一并补 `PACKAGE_NAMES`。
- **后台全量欠账（非本批）**：commit 钩子提示上次后台 `--all --safe`（HEAD eb2a01a，他车道）3 文件红：test_multi_monitor_popups、test_ui_edges_tables、test_ui_batch5_stage_panel_and_script_page；本工作树定向与架构门禁均绿，如实记录待全量轮核验。

## 下一步（T10 后续批次）

- L4 剩余约 81 个顶层实体继续分批（desktop_* 页面族、pet_ui_*、ui_widgets/ui_theme 等共享件、asset_*、storyboard_*、pet_agent 系、app/desktop 本体）；`app.py`/`desktop.py`/`pet_cloud.py`/`writing_api.py` 拆分方案批次。
- L3 收官：`stage_execution_service`（扇出 50）单独一轮；`writing_api` 随拆分；`image_agent_runner` 永久除外。
- 门面清除轮需单独授权。
