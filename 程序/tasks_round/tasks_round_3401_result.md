# R3401 结果文件 — L1 任务书轮 I3：静态反向依赖归零（I3a、I3b）
<!-- round-evidence: {"commit_base": "e4f9c3d2", "credential_hits": 0, "evidence_sha256": "419e4f0c9cfabe71", "exit": 0, "failed": 0, "passed": 57, "round": 3401, "tests": "run_selftests.py -k engine_probe native_apps h3_reference shot_assets layers"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（I3a 模块迁移 1 个＋I3b 注入改造 2 个，合计 3 个模块，未超每子轮 ≤3 上限）。
2. **测试跑了吗、三个基线过了吗？** 跑了。任务书点名 `run_selftests.py -k engine_probe native_apps h3_reference shot_assets layers` **57 条 0 红**；补充 `-k engine_probe native_apps video_revision model_probe_layers layers` **72 条 0 红**；`smoke_test.py` **9/9 绿**；`smoke_test.py --architecture` **541 条全绿**（329.1 秒）；PROJECT_MAP 同步后复跑其守护用例 8 条绿。全量回归未触发（分支不累计欠账，合入 master 前按规则补跑），欠账以 `full-safe-receipts.json` 为准。
3. **欠账少了吗？** 少了。FL-01（L1 静态反向依赖）**3→0**；「层级」豁免台账 **18→15** 且 importer 属 L1 的条目 **3→0**；LR-01 上行边 **21→18**、LR-07 L1 中文 raise **263→257**、LR-09/LR-10 无 `__all__` L1 模块 **57→56**（h3 移出 L1 后口径自然下降）。

## 领号说明

- `round_claim.py next` 分配 **R3401**（claims 登记 `devin-l1-enterprise`／`codex/l1-enterprise`）。R3391 为上一会话已分配未用号，留空不补（编号允许跳空）。

## I3-1　三条豁免删除、test_layers 绿、层级段无 L1 importer ✅

- `维护记录/架构统一基数.json`「层级」段删除 `engine_probe→workflow_engines`、`h3_reference_adapter→shot_assets`、`native_apps→white_model` 三条豁免，`count`/`baseline_exempt` **18→15**；现存 15 条逐一核对 importer 层均非 L1（L0→L1 六条、L2→L3/L4 五条、L3→L4 一条、L2→L4 三条），**importer 属 L1 = 0**。
- `tests/architecture/_layers.py`：`h3_reference_adapter` 自 L1 登记移入 `agent/` 包 L2 登记（`_register(2, ...)`）；新增 `SAME_LAYER_EDGES` 条目 `('h3_reference_adapter', 'shot_assets')`（对应 `from agent.shot_assets import assets`）。
- `test_layers` 6 条、`test_layer_relations` 5 条全绿；LR-01 实测 18（15 条静态豁免＋3 条 `KNOWN_DYNAMIC_UPWARD`），棘轮基线同步下调至 18。

## I3-2　未注入回调返回明确「未配置」，不抛 AttributeError ✅

- `infra/engine_probe.py`：新增 `_COMMAND_BUILDER`＋`register_command_builder(builder)`；`app_argv(..., command_builder=None)` 显式参数优先、否则取登记值，均缺时抛 `ValueError('引擎命令构造器未配置：…')`；`probe()` 只捕获含「未配置」的该异常，落 `verdict='not-configured'`＋`argv_error`，`summary()` 与 `main()`（退出码 1）同步识别；非配置类 `ValueError` 原样上抛（`test_probe_reraises_errors_that_are_not_configuration` 钉住）。
- `infra/native_apps.py`：新增 `_blender_finder`＋`register_blender_finder(finder)`；`open_blender()` 未注入时抛 `ValueError('Blender 查找器未配置：…')`。
- 新增用例：`test_app_argv_without_injected_builder_reports_not_configured`、`test_an_explicit_command_builder_wins`、`test_register_command_builder_installs_the_builder`、`test_probe_without_builder_reports_not_configured`、`test_open_blender_without_injected_finder_reports_not_configured`。既有断言未改。

## I3-3　组装点注入后行为与改前一致 ✅

- `orchestrator/workflow_engines.py`（L3 组装点）：模块级 `from infra import engine_probe as _engine_probe`；`_engine_probe_command_builder` 薄封装转调 `background_command`，模块末尾 `register_command_builder` 自登记——`mock.patch('workflow_engines.background_command')` 补丁面不变（封装在调用期解析模块全局名）。
- `ui/white_model.py`（L4 组装点）：`_registered_blender_finder(refresh=False)` 薄封装转调 `find_blender(refresh)`，模块末尾 `register_blender_finder` 自登记——`mock.patch('white_model.find_blender')` 补丁面不变（`test_native_apps` 既有用例原样通过）。
- `local_video.py:143` 消费者改 `from agent.h3_reference_adapter import attach`（惰性导入，L4→L2 方向正确）；`tests/test_video_revision.py` 两处补丁目标同步为 `agent.h3_reference_adapter.attach`（契约变化：模块路径，断言未动）。
- 裸跑 `python infra/engine_probe.py`（未导入组装点）现在得到明确的 `not-configured` 结论与退出码 1，docstring 跑法已同步为经 `workflow_engines` 导入的调用形态。

## I3a　h3_reference_adapter 上移 L2（迁入 `agent/`）

- `infra/h3_reference_adapter.py` → `agent/h3_reference_adapter.py`（Q2 判为业务语义：H3 Ref2VA 参考资产接入，公开接口面向镜头/资产业务概念；I0 判定 `agent/` 为既有 L2 包归属，优于新建 `domain/` 顶层模块——`agent/shot_assets`、`agent/wan`、`agent/volcengine` 同族视频适配器已在 L2）。
- 唯一 import 改 `from agent.shot_assets import assets`（同包同层）；文件内容其余逐字未动（含 8 处中文 raise 随模块移出 L1，LR-07 口径 263→257）。
- `architecture.md` L2 表登记 `agent/h3_reference_adapter`；`PROJECT_MAP.md` Agent 运行时行同步（含层归属枚举）。
- `维护记录/架构统一基数.json`「第一项」同步：`exempt_items` +`h3_reference_adapter`（`exempt_count` 52→53；该模块不消费 `service_contract`，属已审计豁免）、`historical_name_audit_pending` +同名（顶层裸名 `程序/h3_reference_adapter.py` 不存在，按历史名追溯口径登记）；`test_every_registered_l2_module_has_a_scope_record` 绿。
- 覆盖率基线同步：`覆盖率基数.json` 增 `agent/h3_reference_adapter.py`（44 判定点）、删 `infra/h3_reference_adapter.py`；`分支覆盖率基线.json`（infra 口径 93 模块）移除该条；`engine_probe.py` 判定点 254→270、`native_apps.py` 20→21 点/25%→28.6% 随新代码重测。

## 待切换项／移交

- **端口协议待切换**：G-A4 未满足（`contract/ports.py` 不存在），I3b 注入为带类型注解的普通回调（`builder(config, project, output, report)`、`finder(refresh=...)`），按 §2.4 由 I25 收口切换。
- `project_status.md` 工作树版轮次头同步至 3402（不入提交，合并轮口径处理）。
- LR-01 剩余 18 条上行边（L0→L1 六条、L2/L3→L3/L4 十二条）与 3 条动态上行属其他层存量，收口见 I2/I4/I5/I20。

## 测试证据

- `py -B run_selftests.py -k engine_probe native_apps h3_reference shot_assets layers`（任务书点名）：**57 条用例，9.1 秒，0 红**（test_engine_probe 33、test_native_apps 2、test_model_probe_layers 16、architecture.test_layers 6）。
- `py -B run_selftests.py -k engine_probe native_apps video_revision model_probe_layers layers`（补充覆盖移动模块消费者）：**72 条用例，10.0 秒，0 红**（+test_video_revision 15）。
- `py -B smoke_test.py`（默认）：**9/9 绿**。
- `py -B smoke_test.py --architecture`：**541 条用例，329.061 秒，全绿**（含 test_layers/test_layer_relations/test_service_return_contract/test_project_context_boundary/test_coverage_audit_ratchet 等台账一致性用例）。
- PROJECT_MAP.md 同步后定向复验：`test_three_documents_agree_on_stage_count`、`test_desktop_route_documentation_matches_current_contract`、`test_app_metadata` 共 8 条绿。
- 分支覆盖率复测：`engine_probe.py` **71.7%**（38/53 判定点，棘轮下限 69%）、`native_apps.py` **28.6%**（6/21，下限 5%）；覆盖率基线全量重生成 93 目标模块 112 用例绿。
- 全量 `--all --safe`：本轮未触发（分支口径不累计；合入 master 前按 §5 强制补跑）。

## 改动清单

- `infra/engine_probe.py`：去 `workflow_engines` 反向依赖，`register_command_builder` 注入＋`not-configured` 判定。
- `infra/native_apps.py`：去 `ui.white_model` 反向依赖，`register_blender_finder` 注入＋未配置报错。
- `infra/h3_reference_adapter.py` → `agent/h3_reference_adapter.py`（移动＋import 改 `agent.shot_assets`）。
- `orchestrator/workflow_engines.py`、`ui/white_model.py`：组装点自登记注入。
- `local_video.py`、`tests/test_video_revision.py`：消费路径与补丁目标迁移。
- `tests/test_engine_probe.py`、`tests/test_native_apps.py`：未配置/注入/显式构造器用例。
- `tests/architecture/_layers.py`：L1→L2 登记迁移＋同层边登记。
- `维护记录/架构统一基数.json`：「层级」−3、「第一项」+exempt/historical。
- `维护记录/层间合规清单.json`：LR-01 21→18、LR-07 263→257、LR-09/LR-10 57→56。
- `维护记录/覆盖率基线.json`、`维护记录/分支覆盖率基线.json`：重生成。
- `architecture.md`、`PROJECT_MAP.md`：分层表与模块地图同步。

## 提交

- 分支 `codex/l1-enterprise`；commit 见 `git log`（`dev.py commit` 自动暂存白名单＋生成 `tasks_round/evidence/R3401.json`）。
- 未 push（规则：仅用户明确要求时 push）。

[TASK_COMPLETE]
