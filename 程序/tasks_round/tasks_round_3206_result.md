# R3206 结果：T10 包化——infra/（L1 基础设施层）第四批 3 个中扇出枢纽模块迁移
<!-- round-evidence: {"commit_base": "a5f90320", "credential_hits": 0, "evidence_sha256": "aa5cbd500af6babc", "exit": 0, "failed": 0, "passed": 1566, "round": 3206, "tests": "run_selftests.py -k pet_llm pet_state model_pool pet_agent pet_ui pet_settings pet_cloud pet_report workflow writing_api stage_execution stage_gateway exit_maintenance api model_ money request_ledger"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟、`--affected` 定向、扩展 `-k` 定向、`--architecture` 架构门禁与覆盖率基线结果见验证记录。
3. **欠账少了吗**：是。T10 包化 **infra/ L1 第四批**：`infra/` 实体由 44 → 47 个。L1 顶层剩余 4 个真实实体（storage_maintenance、app_logging、file_cache、ui_tokens）继续分批或专轮；L4/L3 收官项同前轮盘点；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `infra/` 实体 | 3 个中扇出（静态引用边 44–66）顶层 L1 模块 `git mv` 入 `infra/`：pet_llm、pet_state、model_pool。 |
| 别名门面 ×3 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = infra.<名>` 别名门面；实体同一性 3/3 校验通过，`pet_state.PAGE_OF` 经门面解析 len=13 与冒烟期望一致。 |
| 消费方 import | 136 个文件改包路径导入（`import infra.X as X`／`from infra.X import`，含 app/desktop/pet_*/stage_execution_service/writing_api/environment_check/codex_tasks/pet_agent 生产消费边、domain/、orchestrator/、infra/ 域内边与测试文件）；AST 复扫残留 **0 处**，1466 个 .py 全部可解析。 |
| `__file__` 锚点 ×2 | `infra/pet_llm.py`、`infra/model_pool.py` `PROGRAM` 根改 `.parents[1]` 锚回程序根（CONFIG_PATH＝`配置/宠物/配置.json` 语义不变）。 |
| 域内规范 ×3 | `infra/model_pool.py` `model_secrets`/`token_saver`、`infra/pet_llm.py` `stage_layout` 三处历史逗号形态漏网的扁平互引补 `infra.`/`contract.` 前缀（前批批漏，门面兜底未断）。 |
| 日志名冻结 ×1 | `infra/pet_llm.py` `LOGGER = logging.getLogger(__name__)` → `getLogger('pet_llm')`——`__name__` 变 `infra.pet_llm` 会让 `assertLogs('pet_llm')` 捕获落空（test_pet_llm 2 红实测复现后修复）。pet_state/model_pool 无模块级 LOGGER。 |
| 冒烟源路径 ×2 | `smoke_test.py` 轮10两条 keyword 检查 `程序\model_pool.py`→`程序\infra\model_pool.py`（读到门面会拿不到 `'chatgpt-desktop': 'codex'` 字面量）。 |
| 测试契约同步 ×2 | `test_app_logging.py`、`test_app_metadata.py` 各一处顶层路径直读改 `entity_file()` 取径（读门面会让源码断言落空）。断言强度不变，按 §2.4 记录。 |
| 棘轮台账 | `架构统一基数.json` 覆盖率审计21 两个 `model_pool.py` retired 条目改 `infra/` 前缀（relpath 口径对齐）。 |
| 基线与文档 | `architecture.md` infra 目录行「共 44 个」→「共 47 个」；`PROJECT_MAP.md` 模型与安全行 `model_pool.py`/`pet_llm.py` 与密钥判据 `pet_llm.credential` 改包路径；`_layers.py` 扁平登记名天然兼容未改。 |

## 验证记录

- `smoke_test.py`（默认）：首轮 **2 红**（model_pool 门面致 keyword 检查落空），改源路径后 **9/9 通过**。
- `smoke_test.py --affected pet_llm pet_state model_pool`：冒烟 **9/9**；定向按文件名选中 6 个测试文件 166 条——首轮 **2 红**（`assertLogs('pet_llm')` 因 LOGGER 名漂移捕获落空），日志名冻结后复跑 **ALL TESTS PASSED**。
- 扩展 `run_selftests.py -k`（pet_agent/pet_ui/pet_report/pet_settings/pet_cloud/workflow/writing_api/stage_/asset/continuity/api/model_/money/request_ledger/critical_chains/manual_plan/app_logging/app_metadata/storage/exit_maintenance）：选中 **126 个测试文件／2213 条用例／965.7 秒**，首轮 **2 个文件红**——`test_exit_maintenance`（4 红）与 `test_stage_gateway_base`（3 红）。
- **两红根因均为 R3096（门面全删＋codemod）历史欠账、非本批回归**（两测试文件与 master 逐字节一致，相关源码 diff 仅本批 import 路径改写）：①`test_exit_maintenance` 的 patch 目标元组 `('log_maintenance',…)`/`('workspace_maintenance',…)` 为字符串字面量、codemod 未覆盖，门面删除后扁平模块不存在——改 `infra.` 前缀（断言不变，`storage_maintenance` 顶层实体仍在故保留扁平）；②R3096 把 ses 的 `# noqa: F401 re-export` 多行导入收成"仅用名"单行，误删 4 个再导出名（`cloud_video_gateway`/`video_lifecycle_gateway`/`previs_routing_gateway`/`previs_progress_gateway`）使 R2260 网关 façade 契约破裂——按 `ce70e20c~1` 逐名还原。修复后两文件直接复跑 **7/7 绿**；全 tests/ `patch('…')` 扁平目标扫描仅余 `batch_frames_tool`（实体目录，非 casualty）与 `webbrowser`（stdlib）两个误报。
- `smoke_test.py --architecture`：结果见收尾更新（覆盖率基线两轮返工：首测时临时脚本 `_rewrite_r3206.py` 尚在致基线多计 1 模块且架构三项红，删除后重测）。
- 覆盖率：`scripts/coverage_report.py` 重测写入 `维护记录/覆盖率基线.json`（97 条目标用例全通过，**637 模块／72 覆盖**——首轮 638 系临时脚本 `_rewrite_r3206.py` 被计入，删除后重测回落；covered 74→72 系消费方改包路径后 model_secrets/token_saver 等门面不再被 9 组目标用例触达，如实记录）；`runbook.md` §11 同步（637/72/565）。
- 过程插曲（如实）：扩展 `-k` 首轮因 GBK 控制台无法编码 `✗` 回显隐藏桌面日志崩溃（`UnicodeEncodeError`），`PYTHONUTF8=1` 重跑；`round_claim.py next` 同因需 `PYTHONUTF8=1`（R3206 领得，R3205 被并行车道占用）。

## 观察记录（历史欠账，未扩大范围）

- 包内扁平互引历史漏网 **25 处**（扫描 `infra/`/`domain/`/`orchestrator/`/`ui/`/`contract/` 内对已迁移实体的扁平 `import`/`from`）：前批逗号形态 `import A, B` 重写盲区所致，门面兜底不影响运行；本批只修了自己迁移实体内的 3 处，其余留待专门清扫轮或随各模块后续批次顺带处理。
- `architecture.md` §3 L0 行尾部列有 `continuity_ledger`（_layers 登记 L1）——既有文档/登记不一致，同 R3204 记录。
- `storage_maintenance.py` 顶层 `__main__ --cleanup` 子进程入口＋`launch_background` 拉起路径已查明：迁移需配 `__main__` 转发门面（`_scan.is_package_facade` 已支持该形态），留待专轮连同 app_logging/file_cache/ui_tokens 高扇出枢纽一并评估。

## 下一步（T10 后续批次）

- infra/ L1 剩余 4 个真实顶层实体：storage_maintenance(55，`__main__` 特例)、app_logging(81)、file_cache(107)、ui_tokens(149)——file_cache 是正式 JSON 读唯一权威、ui_tokens 被全部 UI 消费、app_logging 是日志枢纽，建议各自专轮或两两分批。
- L4/L3 收官项同前轮：`stage_execution_service`（扇出 50）单独一轮、`writing_api` 随拆分批、`image_agent_runner` 永久除外。
- 门面清除轮需单独授权。
