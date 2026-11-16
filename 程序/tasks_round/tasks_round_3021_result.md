# R3021 结果：T10 包化——domain/（L2 业务层）第二批 24 个模块迁移
<!-- round-evidence: {"commit_base": "5efaee2e", "credential_hits": 0, "evidence_sha256": "03cff5a9afc4c69d", "exit": 0, "failed": 0, "passed": 215, "round": 3021, "tests": "run_selftests.py -k skill_command account_client recon_service writing_stream writing_tools download_inbox desktop_settings_service asset_detail_service keyframe_lifecycle_service local_video_settings_service pet_performance_service pet_test_service previs_progress_service script_preview_service script_structure_edit_controller storyboard_edit_service storyboard_lifecycle storyboard_rows_service storyboard_source_service video_prompt_publication video_source_evidence asset_batch_lifecycle asset_batch_selection_service asset_batch_settings_service"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`smoke_test.py --affected`（24 模块全消费方）50 个测试文件 **ALL TESTS PASSED、0 红文件、461 秒**；`smoke_test.py --architecture` 架构门禁当轮复测 **471/471 全绿**（含 test_layers／test_no_circular_import／test_static_hygiene／test_startup_budget）；覆盖率基线重测 **571 模块／73 覆盖**；`distribution_build.py --verify` 全项 ok。
3. **欠账少了吗**：是。T10 包化推进 domain 第二批：`domain/` 实体由 24 → 48 个，顶层 L2 实体继续收缩。剩余顶层 L2 模块与 L3/L4 各批、`app.py`/`pet_cloud.py`/`writing_api.py` 拆分方案仍是后续批次；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `domain/` 实体 | 24 个 L2 模块 `git mv` 入 `domain/`：account_client、asset_batch_lifecycle、asset_batch_selection_service、asset_batch_settings_service、asset_detail_service、desktop_settings_service、download_inbox、keyframe_lifecycle_service、local_video_settings_service、pet_performance_service、pet_test_service、previs_progress_service、recon_service、script_preview_service、script_structure_edit_controller、skill_command、storyboard_edit_service、storyboard_lifecycle、storyboard_rows_service、storyboard_source_service、video_prompt_publication、video_source_evidence、writing_stream、writing_tools。 |
| 别名门面 ×24 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = domain.<名>` 别名门面（沿用 R2927/R2945 口径：私有名、模块级状态、`mock.patch` 扁平补丁面一致）；24/24 `import <扁平名> is import domain.<名>` 实体同一校验全过。 |
| 消费方 import | 33 个生产文件改包路径导入（desktop.py 内联导入、desktop_* 页面族、engine、idea_chat、keyframe_import、pet_ui_support、previs_progress、storyboard_files、storyboard_source_selector、asset_batch、asset_skill_batch、skill_tools、stage_execution_service、writing_api 及 orchestrator/ 7 个编排文件）；全库 AST 扫描（含 agent/、scripts/、batch_frames_tool/、voice_engine/ 子目录）24 个扁平名残留静态/动态导入 **0 处**。逻辑零改动，仅 import 行。 |
| `__file__` 根锚 | `domain/skill_command.py` 的 skills 根 `Path(__file__).resolve().parent` → `.parents[1]`（实体多下沉一层，解析结果仍为 `程序/skills`）。全库 24 实体复查 `__file__`/`__name__`：仅此 1 处需要锚点修正；`account_client` 的 `type(exc).__name__` 为异常类名，与模块名无关。 |
| 日志名冻结 | 7 个实体 `logging.getLogger(__name__)` → `getLogger('<扁平名>')`（asset_batch_settings_service、asset_detail_service、desktop_settings_service、storyboard_edit_service、video_prompt_publication、writing_tools 等），日志名不随包路径漂移。 |
| 边界测试包感知 | 11 个架构测试改 `entity_file()` 取径实体源码，不再读顶层薄门面：test_asset_batch_settings_boundary、test_asset_detail_binding_boundary、test_keyframe_replace_boundary、test_local_video_settings_boundary、test_video_prompt_publication_boundary、test_json_io_boundary、test_writing_publication_boundary、test_project_entry_boundary、test_project_context_boundary（新增 `_source()` 助手统一取径）、test_service_return_contract（3 处）、test_coverage_baseline（CORE_FLOORS 两键改 `domain/` 路径）。断言语义未动。 |
| 棘轮台账 | `架构统一基数.json` 第四项 1 条 `account_client.py`（exempt）file 改 `domain/account_client.py`（第四项沿用 relpath 口径，已迁模块先例同）；第三项沿用 basename 口径未动。`_layers.py` 扁平登记名与 `registry_key` 归一天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **571 模块／73 覆盖**（547+24 实体；门面计入生产模块集与既有批次口径一致）；`runbook.md` §11 同步（571/73/498）；`architecture.md` domain 目录树「首批 22 个」→「共 48 个」；`PROJECT_MAP.md` 阶段配置行 `skill_command.py` → `domain/skill_command.py`；`distribution_manifest.md` `程序/domain/**` glob 已覆盖无需改；`smoke_test.py` 无本批模块检查项。 |
| 动态字符串核对 | `import_module`/`__import__` 全库扫描无本批模块动态导入；`h3_launcher.pyw`、`ui_plugin_registry`、`stage_handler_registry` 无引用；`contract/artifact_schema.py` 的 `'owner': 'recon_service'` 为产物 owner 持久化键（非导入路径，扁平名经门面仍有效），保持原样——同 R2945 对 owner/kind 键的处置口径。 |

## 验证记录

- `smoke_test.py`（主工作区解释器）：8/8 通过。
- `smoke_test.py --architecture`：首轮 19F+2E（边界/审计测试读顶层门面＋覆盖率基线未刷新）→ 全部定位修复后复测 **471/471 全绿**（当轮实测二轮，177.6s）。
- 定向：`smoke_test.py --affected <24 模块名>` → run_selftests `--serial -k <别名+直接消费方>`，**50 个测试文件全部通过、0 红、461 秒**（Tk 段曾在跨树 GUI 令牌队列等待约 6 分钟，按规则排队后正常取得令牌执行完毕）。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入（97 条目标用例全通过）；`test_coverage_baseline` 5/5 绿。
- 分发：`distribution_build.py --plan` undecided=0；`--build --destination <临时目录>` 2283 文件；`--verify` 全项 ok（no_excluded/keep_present 含运行环境/digest/jingju_package）。工作树缺 `运行环境/`，已建 junction 指向主工作区副本完成校验（junction 受 `.gitignore` `/运行环境/` 规则排除，不入提交）。
- 导入冒烟：24 个 `domain.*` 实体 + 24 个扁平门面全部可导入且对象同一（`ALL ALIAS OK`）；生产侧 24 扁平名静态/动态导入残留 0。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按凭据口径执行；本轮为结构搬迁，未触发启动路径/Tk 生命周期/删除语义新增风险）。

## 过程损耗（如实）

- **轮次号漂移**：前轮会话按 R3009 推进本批搬家但未及提交；本轮开工时 `round_claim.py next` 按当前计数器领得 **R3021** 并自动建 `codex/wip-R3021` 分支承接全部未提交改动，`codex/wip-R3009` 分支留有同名未提交现场的空壳（无提交）。本结果文件与提交按 R3021 记账；R3009 号位未被占用可再领。
- **门禁取径漏改**：11 个边界/审计测试直接 `(ROOT / '<模块>.py')` 读源码，搬家后读到 9 行门面导致断言落空（19F+2E）；按 `_scan.entity_file()` 既定口径逐个改取径，`test_project_context_boundary` 以 `_source()` 助手统一 18 处读取点。`架构统一基数.json` 第四项 relpath 口径的 `account_client.py` exempt 条目同步改 `domain/` 前缀。
- **临时文件**：上一会话遗留的 `程序/dep_scan_tmp.json`（依赖扫描草稿，未跟踪）使 `distribution_build.py --plan` 出现 1 条 undecided，确认为草稿后删除。

## 下一步（T10 后续批次）

- `domain/`（L2）剩余顶层实体继续按族分批同法迁移；L3 中扇出与重枢纽、L4 大模块（desktop_*、pet_ui_*、ui_widgets、app）逐批推进。
- `app.py`、`pet_cloud.py`（实体已在 ui/）、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
- 全部实体入包后另立清理轮移除顶层别名门面（需单独授权）。
