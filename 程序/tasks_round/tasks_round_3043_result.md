# R3043 结果：T10 包化——domain/（L2 业务层）第四批 7 个模块迁移（L2 顶层收尾）
<!-- round-evidence: {"commit_base": "73a17024", "credential_hits": 0, "evidence_sha256": "6bb984f217a139ef", "exit": 0, "failed": 0, "passed": 370, "round": 3043, "tests": "run_selftests.py -k writing asset_context asset_batch_service asset_batch_state_service white_model_service idea_chat storyboard_catalog_service"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`run_selftests.py -k <7 模块名>` 27 个测试文件 370 条全绿（195.4 秒）；`smoke_test.py --affected <7 模块名>` 定向回归 **0 红文件、593 秒门禁通过**；`smoke_test.py --architecture` 架构门禁 **471/471 全绿**（152.7 秒，当轮二轮复测）；覆盖率基线重测 597 模块／74 覆盖。
3. **欠账少了吗**：是。T10 包化 **domain/ L2 顶层迁移收尾**：`domain/` 实体由 67 → 74 个，顶层 L2 实体清零（`_layers.py` L2 登记名全部有 domain/ 实体或历史门面对应）。剩余工作转入 L3 中扇出与重枢纽、L4 大模块（desktop_*、pet_ui_*、ui_widgets、app）各批；`app.py`/`pet_cloud.py`/`writing_api.py` 拆分方案仍是后续批次；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `domain/` 实体 | 7 个顶层 L2 模块 `git mv` 入 `domain/`：asset_batch_service、asset_batch_state_service、asset_context、idea_chat、storyboard_catalog_service、white_model_service、writing——顶层 L2 候选清零（前批 ≤6 扇出筛选后的全部剩余，扇出 7–15 的重枢纽级业务服务）。 |
| 别名门面 ×7 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = domain.<名>` 别名门面；7/7 `import <扁平名> is import domain.<名>` 实体同一校验全过。 |
| 消费方 import | 61 个生产文件改包路径导入（58 个外部消费方＋域内 3 条同批边：asset_batch_state_service→asset_batch_service、asset_context→storyboard_catalog_service、storyboard_catalog_service→writing）；全库 AST 复扫本批 7 扁平名静态/动态裸导入 **0 处**；动态 `import_module`/`__import__` 无本批引用。逻辑零改动，仅 import 行。 |
| `__file__` 根锚 ×2 | `domain/writing.py` 两处 `Path(__file__).resolve().parent` → `.parents[1]`：L46 skills 技能文件根、L102 `import_project` 的 `Projects(app)` 应用根（实体多下沉一层，解析结果仍为 `程序/`）。全库 7 实体复查 `__file__`/`__main__`：仅此模块需要锚点修正。 |
| 日志名冻结 | `domain/writing.py` `logging.getLogger(__name__)` → `getLogger('writing')`，日志名不随包路径漂移。 |
| 边界测试包感知 | 5 个架构测试改 `entity_file()` 取径实体源码：test_asset_batch_ledger_boundary、test_manual_creative_publication_boundary（idea_chat）、test_white_model_service_json_boundary（2 处）、test_writing_preparation_path_boundary、test_writing_publication_boundary（writing 2 处）；另按 `test_storyboard_edit_boundary` 既有双拼写先例，`test_asset_batch_ledger_boundary` 与 `test_final_bundle_boundary` 的 `node.module ==` 扁平比较改 `in {扁平名, domain.扁平名}` 集合（后者同时修复 assertNotIn 语义被包路径前缀架空的隐患）。test_complexity_ratchet 的 `('idea_chat.py','receive_brief')` 参数棘轮与 test_agents_md 的 `asset_batch_service.py` 步骤文案白名单均按 `path.name`/basename 口径天然兼容，未改；test_project_context_boundary 沿用 `_source()`/`_tree()` 助手无需改。断言语义未动。 |
| 棘轮台账 | `架构统一基数.json` 第三项（basename 口径）10 条与「层级」节 2 条 exempt 均按扁平文件名登记，`domain/` 实体扫描名不变，未动；第四项/第五项 relpath 口径本批无命中。`_layers.py` 扁平登记名天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **597 模块／74 覆盖**（590+7 实体）；`runbook.md` §11 同步（597/74/523）；`architecture.md` domain 目录树「共 67 个」→「共 74 个」；`distribution_manifest.md` glob 已覆盖；`PROJECT_MAP.md` 无本批模块路径引用。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过。
- `run_selftests.py -k <7 模块名>`：27 个测试文件 370 条用例全绿、0 红、195.4 秒（GUI 段经跨树令牌队列排队后正常执行）。
- `smoke_test.py --affected <7 模块名>`：run_selftests `--serial -k <7 模块名＋全部直接/间接消费方>` **ALL TESTS PASSED、0 个文件有红、593 秒**（含 test_idea_chat 全族、test_writing_* 全族、test_asset_*、test_white_model_*、test_storyboard_*、test_workflow_*、test_ui_edges_*、test_desktop_startup_perf 等；Tk 段经跨树令牌队列排队后正常执行；1 条登记跳过为发行包 bundled skill 实机复验项，与本批无关）。
- `smoke_test.py --architecture`：首轮 471 项中 1 红——`test_asset_batch_ledger_boundary` 要求 `asset_batch_execution` 以 `from asset_batch_state_service import` 取台账函数，包路径改写后 `node.module` 变 `domain.` 前缀落空；按 `test_storyboard_edit_boundary` 既有 `in {扁平, 包路径}` 双拼写先例修 2 处（`asset_batch_state_service`、`storyboard_storage`），复测 **471/471 全绿（152.7 秒）**。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入（97 条目标用例全通过）。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按凭据口径执行；本轮为结构搬迁，未触发启动路径/Tk 生命周期/删除语义新增风险）；`distribution_build --verify`（同 R3024 口径说明）。

## 过程损耗（如实）

- **轮次号**：`round_claim.py next` 领得 **R3043**（3025–3042 号位已被并行车道占用）；新建 `codex/wip-R3043` 分支叠加在 `codex/wip-R3024`（73a17024）之上承接本批。
- **`node.module` 包路径比较**：`--affected` 全绿但 `--architecture` 抓出 1 红——边界测试按扁平模块名比对 ImportFrom 来源，`domain.` 前缀导致断言落空（另有 1 处 assertNotIn 因同一原因语义被架空，一并按双拼写先例修复，未弱化断言）。
- **分支命名插曲**：领号输出返回前先按旧推断建了 `codex/wip-R3027`，领到 3043 后 `git branch -m` 改名，无内容影响。

## 下一步（T10 后续批次）

- L2 顶层迁移已清零；转入 **L3**（编排层）剩余顶层实体按扇出分批迁 `orchestrator/`，再 **L4**（desktop_*、pet_ui_*、ui_widgets、app 等 UI 层）迁 `ui/`。
- `app.py`、`pet_cloud.py`（实体已在 ui/）、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
- 全部实体入包后另立清理轮移除顶层别名门面（需单独授权）。
