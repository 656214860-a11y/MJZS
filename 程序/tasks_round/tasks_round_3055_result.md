# R3055 结果：T10 包化——orchestrator/（L3 编排层）第一批 6 个低扇出模块迁移
<!-- round-evidence: {"commit_base": "dd02e337", "credential_hits": 0, "evidence_sha256": "6a2e78c77d3b7303", "exit": 0, "failed": 0, "passed": 437, "round": 3055, "tests": "run_selftests.py -k engine stage_flow stage_completion skill_inline keyframe_model workflow continuity delivery storyboard_final"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`run_selftests.py -k <关键词组>` 31 个测试文件 437 条全绿（37.9 秒）；`smoke_test.py --architecture` 架构门禁 471 项（首轮 1 红＝状态页轮次头陈旧，按先例临时同步后复测）；覆盖率基线重测 603 模块／74 覆盖。
3. **欠账少了吗**：是。T10 包化 **orchestrator/ L3 首批**：`orchestrator/` 实体由 59 → 65 个。剩余 L3 顶层 10 个（stage_execution_service 扇出 50、storyboard_selection 24、workflow_settings 22、stage_parallel/stage_config 13、project_context_factory 12、stage_models/skill_registry 11、stage_completion_service 已迁、writing_api 9 中除已迁 6 个外余 9 个重枢纽级模块）按扇出继续分批；L4 顶层 121 个实体随后分批迁 `ui/`；`image_agent_runner` 经核查为子进程入口脚本（`__main__`＋`__file__` 自寻址命令行），不在包化范围；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `orchestrator/` 实体 | 6 个低扇出（0–8）顶层 L3 模块 `git mv` 入 `orchestrator/`：skill_inline、keyframe_model_service、engine、stage_flow、workflow_engines、stage_completion_service。 |
| 排除项 | `image_agent_runner`（扇出 3）**不迁**：L12/L109 `__file__` 自寻址＋L124 `__main__` 子进程入口，`python <自身路径> --project --manifest` 由父进程拼接；入包后 `__main__` 直跑会因 `domain/`式 sys.path 错位与 `batch_frames_tool/config.json` 相对锚点双双失效，属脚本入口而非库模块。 |
| 别名门面 ×6 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = orchestrator.<名>` 别名门面；6/6 `import <扁平名> is import orchestrator.<名>` 实体同一校验全过。 |
| 消费方 import | 25 个生产文件改包路径导入（18 个顶层消费方＋7 个 orchestrator/ 内消费方），`import X` → `import orchestrator.X as X`、`from X import` → `from orchestrator.X import`；全库 AST 复扫本批 6 扁平名静态/动态裸导入 **0 处**；批内实体互不引用（无同批边）；动态 `import_module` 仅命中非本批模块（workflow_settings、white_model）。逻辑零改动，仅 import 行。 |
| `__file__` 锚点 ×1 | `orchestrator/skill_inline.py` L29 `Path(__file__).resolve().parent` → `.parents[1]`（`model_pool.pool(program=…)` 需 `程序/` 根，实体下沉一层后解析结果不变）。全库 6 实体复查 `__file__`/`__main__`：仅此模块需要锚点修正。 |
| 日志名冻结 | `orchestrator/engine.py` `logging.getLogger(__name__)` ×2 → `getLogger('engine')`，日志名不随包路径漂移。 |
| 测试取径 ×6 | 架构测试 ×2 改 `entity_file()`：test_edit_publication_boundary、test_video_publication_boundary（engine.py）；功能测试 ×4 改 `Path(<模块>.__file__)` 随门面取实体：test_continuity_scope、test_delivery_scope、test_storyboard_final_scope（stage_completion_service，补 import）、test_engine_probe（workflow_engines，补 import）。断言语义未动。 |
| 棘轮台账 | `架构统一基数.json` 第四项（relpath 口径）4 条 `workflow_engines.py` exempt → `orchestrator/workflow_engines.py`；「层级」节 engine_probe→workflow_engines exempt 与覆盖率审计24 retired 条按既有口径未动。`_layers.py` 扁平登记名天然兼容，未改。 |
| 基线与文档 | `覆盖率基线.json` 重测 **603 模块／74 覆盖**（597+6：6 实体入 orchestrator/＋6 顶层门面新壳）；`runbook.md` §11 同步（603/74/529）；`architecture.md` orchestrator 目录树「四批共 59 个」→「五批共 65 个」；`distribution_manifest.md` `程序/orchestrator/**` glob 已覆盖；`PROJECT_MAP.md` 三处路径引用改 `orchestrator/` 前缀（stage_flow、workflow_engines、engine）。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过。
- `run_selftests.py -k engine stage_flow stage_completion skill_inline keyframe_model workflow continuity delivery storyboard_final`：31 个测试文件 437 条用例全绿、0 红、37.9 秒（GUI 段经跨树令牌队列排队后正常执行；0 条登记跳过）。
- `smoke_test.py --architecture`：首轮 471 项中 1 红——`test_round_number_continuous` 状态页轮次头 3006 陈旧（最新结果 R3043，应为 3044）；按先例临时同步状态头复测。
- 覆盖率：`scripts/coverage_report.py <基线 9 组 targets> --json 维护记录/覆盖率基线.json` 重测写入（97 条目标用例全通过）。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按凭据口径执行）；`distribution_build --verify`（同前批口径）。

## 过程损耗（如实）

- **轮次号**：`round_claim.py next` 领得 **R3055**；新建 `codex/wip-R3055` 分支叠加在 `codex/wip-R3043`（dd02e337）之上承接本批。
- **`--architecture` 误用**：`run_selftests.py --architecture` 不被识别（该脚本无此参数，0 匹配空跑）；正确入口为 `smoke_test.py --architecture`，已按 runbook §命令表纠正。
- **状态页轮次头**：验证期临时同步为最新结果轮次＋1，未提交（仅 master 提交 project_status.md，合并轮维护）。

## 下一步（T10 后续批次）

- L3 剩余 9 个顶层实体按扇出继续分批：下一批可取 stage_completion_service 同级的 stage_models(11)/skill_registry(11)/project_context_factory(12) 或 workflow_settings(22)/storyboard_selection(24) 中扇出相近组；`stage_execution_service`（扇出 50，阶段执行网关）建议单独一轮；`writing_api`（954 行）随拆分方案批次。
- L4 顶层 121 个实体随后分批迁 `ui/`；`app.py`/`pet_cloud.py`/`writing_api.py` 拆分方案仍是后续批次；门面清除轮需单独授权。
