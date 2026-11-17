# R3024 结果：T10 包化——domain/（L2 业务层）第三批 19 个模块迁移
<!-- round-evidence: {"commit_base": "cdb4a355", "credential_hits": 0, "evidence_sha256": "ee6d553d5c113433", "exit": 0, "failed": 0, "passed": 122, "round": 3024, "tests": "run_selftests.py -k task_center_service usage_overview asset_generated_import_service projects cloud_video_service entitlement_service asset_resume edit_export keyframe_evidence storyboard_adoption_contract workflow_context script_workspace_service video_task_state writing_quality asset_plan keyframe_batch previs_routing project_naming storyboard_storage"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`run_selftests.py -k <19 模块名>` 14 个测试文件 122 条全绿（78.3 秒）；`smoke_test.py --affected <19 模块名>` 定向回归 **2421 条用例／693.9 秒／1 个文件有红**（test_project_recovery 源读顶层门面，已修后该文件 7/7 绿）；`smoke_test.py --architecture` 架构门禁 **471/471 全绿**（209.1 秒，当轮二轮复测；首轮 2 红——台账 relpath 与状态页轮次头——均已定位修复）；覆盖率基线重测 590 模块／74 覆盖。
3. **欠账少了吗**：是。T10 包化推进 domain 第三批：`domain/` 实体由 48 → 67 个，顶层 L2 实体继续收缩。剩余顶层 L2 模块（writing、asset_context、asset_batch_service、asset_batch_state_service、white_model_service、idea_chat、storyboard_catalog_service）与 L3/L4 各批、`app.py`/`pet_cloud.py`/`writing_api.py` 拆分方案仍是后续批次；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `domain/` 实体 | 19 个低扇出（静态+动态扇出 ≤6）L2 模块 `git mv` 入 `domain/`：asset_generated_import_service、asset_plan、asset_resume、cloud_video_service、edit_export、entitlement_service、keyframe_batch、keyframe_evidence、previs_routing、project_naming、projects、script_workspace_service、storyboard_adoption_contract、storyboard_storage、task_center_service、usage_overview、video_task_state、workflow_context、writing_quality。 |
| 别名门面 ×19 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = domain.<名>` 别名门面（沿用 R2927/R2945/R3021 口径）；19/19 `import <扁平名> is import domain.<名>` 实体同一校验全过，`Projects`/`plan_file`/`resolved_alias` 等关键属性抽查在位。 |
| 消费方 import | 60 个生产文件改包路径导入（57 个外部消费方＋域内 4 条同批边）；顶层残留模块（asset_context、asset_batch_service、storyboard_catalog_service、writing、white_model_service 等）同步改 `domain.` 前缀；全库 AST 复扫本批 19 扁平名静态/动态裸导入 **0 处**（`_package_target` 归一口径下 `import domain.X` 正确登记为对 X 的依赖）。域内同批互引同步改 `domain.` 前缀；`storyboard_adoption_contract` 的 `import_module('storyboard_storage')` 动态串改 `domain.storyboard_storage`。逻辑零改动，仅 import 行。 |
| 日志名冻结 | 7 个实体 `logging.getLogger(__name__)` → `getLogger('<扁平名>')`（projects、cloud_video_service、asset_resume×2、workflow_context、script_workspace_service、asset_plan、storyboard_storage），日志名不随包路径漂移。 |
| `__file__`/`__main__` 预检 | 19 实体 `__file__` 引用 0 处、`__main__` 守卫 0 处，无需锚点修正。 |
| 边界测试包感知 | 10 个架构测试改 `entity_file()` 取径实体源码：test_asset_generated_import_boundary、test_asset_plan_publication_boundary（3 处）、test_cloud_video_settings_boundary、test_final_bundle_boundary、test_keyframe_batch_json_boundary、test_previs_routing_publication_boundary、test_stage_display_boundary（STAGE_LABEL_SITES 循环统一取径）、test_writing_publication_boundary（workflow_context）、test_startup_budget（STARTUP_CHAIN 的 projects.py）、test_unification_ratchet（_projects_direct_storage_calls）；test_coverage_baseline CORE_FLOORS `usage_overview.py` → `domain/usage_overview.py`；功能测试 test_project_recovery 的 projects 源读改 `inspect.getfile(Projects)` 取实体路径。断言语义未动。 |
| 棘轮台账 | `架构统一基数.json` 第四项（relpath 口径）2 条 exempt file 改 `domain/` 前缀：writing_quality.py、script_workspace_service.py；第三项沿用 basename 口径、覆盖率审计各段 retired 条目不重扫，均未动。`_layers.py` 扁平登记名与 `registry_key` 归一天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **590 模块／74 覆盖**（571+19 实体；门面计入生产模块集与既有批次口径一致）；`runbook.md` §11 同步（590/74/516）；`architecture.md` domain 目录树「共 48 个」→「共 67 个」；`distribution_manifest.md` `程序/domain/**` glob 已覆盖无需改；`PROJECT_MAP.md` 无本批模块路径引用。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过。
- `run_selftests.py -k <19 模块名>`：14 个测试文件 122 条用例全绿、0 红、78.3 秒（GUI 段经跨树令牌队列正常排队取得）。
- `smoke_test.py --affected <19 模块名>`：run_selftests `--serial -k <19 模块名＋直接消费方>` 共 **2421 条用例、693.9 秒、1 个文件有红**——`test_project_recovery.test_project_layer_never_permanently_removes` 以 `(desktop.__file__).parent/'projects.py'` 读源码断言 `recycle_paths` 在场，搬家后读到 9 行门面；改经 `inspect.getfile(Projects)` 取实体真实路径（断言语义不变，且更贴运行时真实模块），复测该文件 **7/7 绿**。其余 2420 条首轮全绿。
- `smoke_test.py --architecture`：首轮 471 项中 2 红——`test_bare_json_load_debt_is_a_nonincreasing_subset`（台账第四项 relpath 未随搬家前缀，2 条 exempt file 改 `domain/` 后该项 4/4 绿）与 `test_round_number_continuous`（状态页轮次头 3006 滞后属合并轮同步项，按先例临时同步至本轮结果+1 复测）；复测 **471/471 全绿（209.1 秒）**。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入（97 条目标用例全通过）；`test_coverage_baseline` 相关项随架构复测核验。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按凭据口径执行；本轮为结构搬迁，未触发启动路径/Tk 生命周期/删除语义新增风险）；`distribution_build --verify`（上批 R3021 已验证 manifest glob 覆盖，本批同口径文件集合增量为同类实体＋门面）。

## 过程损耗（如实）

- **轮次号**：`round_claim.py next` 领得 **R3024**（3022/3023 号位已被并行车道占用）；新建 `codex/wip-R3024` 分支叠加在 `codex/wip-R3021`（cdb4a355）之上承接本批，避免与未合并批次的 import 改写面冲突。
- **功能测试源读**：`--affected` 复跑抓出 `test_project_recovery` 1 红——它按 `desktop.__file__` 同级拼 `projects.py` 读源码，门面化后读到转发壳；改取 `Projects` 类的 `inspect.getfile` 实体路径，断言三件套（recycle_paths 在场／无 rmtree／无 unlink()）原样保留。
- **状态页轮次头**：`project_status.md` 当前轮次 3006 为 master 合并轮维护项；按 R2980/R3021 先例在验证期临时同步为「最新结果轮次+1」通过连续性门禁，该文件不随功能分支提交，由 master 合并轮统一更新。

## 下一步（T10 后续批次）

- `domain/` 剩余 7 个顶层 L2 实体（writing、asset_context、asset_batch_service、asset_batch_state_service、white_model_service、idea_chat、storyboard_catalog_service，扇出 7–15）收尾同法迁移；L3 中扇出与重枢纽、L4 大模块（desktop_*、pet_ui_*、ui_widgets、app）逐批推进。
- `app.py`、`pet_cloud.py`（实体已在 ui/）、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
- 全部实体入包后另立清理轮移除顶层别名门面（需单独授权）。
