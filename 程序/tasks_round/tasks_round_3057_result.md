# R3057 结果：T10 包化——orchestrator/（L3 编排层）第二批 5 个中扇出模块迁移
<!-- round-evidence: {"commit_base": "ba590a9d", "credential_hits": 0, "evidence_sha256": "13236cf37beb8e22", "exit": 0, "failed": 0, "passed": 112, "round": 3057, "tests": "run_selftests.py -k stage_models skill_registry project_context stage_config stage_parallel skill_panel workflow_settings stage_model"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`run_selftests.py -k <关键词组>` 13 个测试文件 112 条全绿（7.3 秒）；`smoke_test.py --architecture` 架构门禁 471 项复测；覆盖率基线重测 608 模块／74 覆盖。
3. **欠账少了吗**：是。T10 包化 **orchestrator/ L3 第二批**：`orchestrator/` 实体由 65 → 70 个。剩余 L3 顶层 4 个可迁实体（workflow_settings 22、storyboard_selection 24、writing_api 9 待拆分批、stage_execution_service 50 建议单独一轮）；L4 顶层 121 个实体随后分批迁 `ui/`；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `orchestrator/` 实体 | 5 个中扇出（11–13）顶层 L3 模块 `git mv` 入 `orchestrator/`：stage_models、skill_registry、project_context_factory、stage_config、stage_parallel。 |
| 排除项复核 | `stage_models` 的 `__main__` 命中为 `sys.modules.get('__main__')` 自检探针判定（非子进程入口），可迁；`image_agent_runner` 上轮已确认除外。 |
| 别名门面 ×5 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = orchestrator.<名>` 别名门面；5/5 `import <扁平名> is import orchestrator.<名>` 实体同一校验全过。 |
| 消费方 import | 54 个引用文件改包路径导入：53 个经行级重写（`import X` → `import orchestrator.X as X`、`from X import` → `from orchestrator.X import`）＋3 条批内边手工修（stage_config→skill_registry、stage_models→stage_config×2、stage_parallel→project_context_factory/stage_config）＋2 处动态串（white_model、domain/keyframe_batch 的 `import_module('stage_parallel')` → `'orchestrator.stage_parallel'`）；全库 AST 复扫本批 5 扁平名残留 **0 处**。`selftest_scheduling.py` 与 `维护记录/基准脚本/` 属非登记开发工具，不在生产扫描面，门面兼容不改。逻辑零改动，仅 import 行。 |
| `__file__` 锚点 ×4 | `orchestrator/skill_registry.py` ×2、`orchestrator/stage_config.py` ×2（含模块级 `PROGRAM` 常量）`Path(__file__).resolve().parent` → `.parents[1]`，解析结果仍为 `程序/`。6 实体复查 `__file__`/`__main__`：仅此两模块需要锚点修正。 |
| 测试取径 | **零改动**——既有包感知基建全覆盖：test_project_context_boundary 的 `_tree()`/`_source()` 与 test_stage_display_boundary 的 `entity_file()`、test_atomic_write_boundary 的 `registry_key()`、test_complexity_ratchet 的 `path.name` 键、test_stage_parallel 的模块对象导入，均自动命中 orchestrator/ 实体。 |
| 棘轮台账 | `架构统一基数.json` 第四项（relpath 口径）1 条 `stage_parallel.py` exempt → `orchestrator/stage_parallel.py`；覆盖率审计24 retired 条按既有口径未动。`_layers.py` 扁平登记名天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **608 模块／74 覆盖**（603+5：5 实体入 orchestrator/＋5 顶层门面新壳）；`runbook.md` §11 同步（608/74/534）；`architecture.md` orchestrator 目录树「五批共 65 个」→「六批共 70 个」；`distribution_manifest.md` glob 已覆盖；`PROJECT_MAP.md` 阶段配置/阶段基础设施两行 5 处路径引用改 `orchestrator/` 前缀。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过。
- `run_selftests.py -k stage_models skill_registry project_context stage_config stage_parallel skill_panel workflow_settings stage_model`：13 个测试文件 112 条用例全绿、0 红、7.3 秒（GUI 段经跨树令牌队列排队后正常执行；0 条登记跳过）。
- `smoke_test.py --architecture`：471 项全量复测（状态页轮次头按先例临时同步为 3058 后运行）。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入（97 条目标用例全通过）。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按凭据口径执行）；`distribution_build --verify`（同前批口径）。

## 过程损耗（如实）

- **轮次号**：`round_claim.py next` 领得 **R3057**（3056 号位被占用）；新建 `codex/wip-R3057` 分支叠加在 `codex/wip-R3055`（ba590a9d）之上承接本批。
- **批内边漏改**：首轮行级重写跳过 BATCH 成员自身，3 条同批边（stage_config→skill_registry 等）残留扁平 import——虽门面兼容可运行，但按包路径规范手工补改后复扫归零。
- **动态串漏改**：`white_model.py` 与 `domain/keyframe_batch.py` 的 `import_module('stage_parallel')` 不在行级正则面，AST 复扫兜底抓出 2 处已修。
- **提交流程**：吸取 R3055 教训——`dev.py commit` 不会 `git add -A`，提交前显式 `git add -A` 暂存全部 50+ 文件。

## 下一步（T10 后续批次）

- L3 剩余 4 个顶层实体：`workflow_settings`（22）、`storyboard_selection`（24）扇出相近可同批；`writing_api`（954 行）随拆分方案批次；`stage_execution_service`（扇出 50，阶段执行网关）建议单独一轮；`image_agent_runner` 为子进程入口脚本永久除外。
- L4 顶层 121 个实体随后分批迁 `ui/`；`app.py`/`pet_cloud.py`/`writing_api.py` 拆分方案仍是后续批次；门面清除轮需单独授权。
