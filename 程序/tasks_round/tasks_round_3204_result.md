# R3204 结果：T10 包化——infra/（L1 基础设施层）第三批 5 个低扇出模块迁移
<!-- round-evidence: {"commit_base": "1ac36844", "credential_hits": 0, "evidence_sha256": "38c38cddba092c1f", "exit": 0, "failed": 0, "passed": 373, "round": 3204, "tests": "run_selftests.py -k continuity_ledger api_endpoints project_settings ui_plugin_registry model_router api model_pool manual_plan continuity env_key dynamic_import http_boundary secret_sink asset_batch_settings project_settings"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟、`--affected` 定向、`--architecture` 架构门禁与覆盖率基线结果见验证记录。
3. **欠账少了吗**：是。T10 包化 **infra/ L1 第三批**：`infra/` 实体由 39 → 44 个。L1 顶层剩余 7 个真实实体（pet_llm、pet_state、model_pool、storage_maintenance、app_logging、ui_tokens、file_cache，扇出 44–149 的中高扇出枢纽）继续分批或专轮；L4/L3 收官项同前轮盘点；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `infra/` 实体 | 5 个低扇出（静态引用边 16–37）顶层 L1 模块 `git mv` 入 `infra/`：continuity_ledger、api_endpoints、project_settings、ui_plugin_registry、model_router。 |
| 别名门面 ×5 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = infra.<名>` 别名门面；`import <扁平名> is import infra.<名>` 实体同一性 5/5 校验通过。 |
| 消费方 import | 102 个文件改包路径导入（`import infra.X as X`／`from infra.X import` 惯例，含 app/desktop/pet_*/model_pool/stage_execution_service/writing_api 生产消费边、domain/、orchestrator/、ui/、agent/、infra/ 域内边、维护记录基准脚本与测试文件）；AST 复扫残留 1 处行内内联 import（`orchestrator/storyboard_final.py:115`），已手工补 `infra.` 前缀后复扫 **0 处**。测试文件同步改包路径（与前几批口径一致），`mock.patch` 扁平名经门面实体同一性不受影响。 |
| `__file__` 锚点 ×1 | `infra/model_router.py` `PROGRAM` 根改 `.parents[1]` 锚回程序根（`self.program` 供配置/环境文件定位，语义不变）。 |
| 批内边 ×1 | `infra/model_router.py` `from api_endpoints import …` → `from infra.api_endpoints import …`（同批成员互引）。 |
| 棘轮台账 | `架构统一基数.json` 6 个 `file` 条目随包迁移改 `infra/` 前缀（第四项 4 项：continuity_ledger retired×2、api_endpoints json.loads×2——后者点锚按 relpath 匹配必须带前缀；覆盖率审计21/26 各 1 项 retired 同步对齐）。dispostion/reason/point 全保留。 |
| HTTP 白名单 | `test_http_boundary.py` ALLOWED `api_endpoints.py`→`infra/api_endpoints.py`（存量直连点跟随实体路径，白名单口径不变）。 |
| 测试契约同步 ×2 | `test_continuity_publication_boundary.py` 改 `entity_file('continuity_ledger')` 取径（原读顶层门面会拿到 9 行壳）；`test_asset_batch_settings_boundary.py` 断言 `('project_settings','read_prefs')`→`('infra.project_settings','read_prefs')`。断言强度不变，按 §2.4 记录。 |
| 基线与文档 | `architecture.md` infra 目录行「共 39 个」→「共 44 个」；`PROJECT_MAP.md` `model_router.py`/`continuity_ledger.py` 两处路径改 `infra/` 前缀；`_layers.py` 扁平登记名天然兼容未改；`distribution_manifest.md` glob 已覆盖；`smoke_test.py` 无本批模块源路径检查。 |

## 验证记录

- `smoke_test.py`（默认）：**9/9 通过**。
- `smoke_test.py --affected continuity_ledger api_endpoints project_settings ui_plugin_registry model_router`：冒烟检查项 **9/9**；定向门禁按文件名匹配选中 3 个测试文件（test_continuity_ledger/test_model_router_diagnostics/test_model_router_parse），31 条用例 0 红，冒烟合计 **10/10 通过**。
- 定向 `run_selftests.py -k`（test_api/test_model_pool/test_manual_plan/test_continuity/test_env_key/test_dynamic_import/test_http_boundary/test_secret_sink/test_asset_batch_settings/test_project_settings）：**18 个测试文件／264 条用例／0 红／ALL TESTS PASSED**（含本批修复的 4 个架构边界测试与 manual_plan 的 ui_plugin_registry 打桩面）。
- `smoke_test.py --architecture`：首轮 **1 红**（`test_round_number_continuous`——状态页轮次头按惯例临时同步 3205，仅 master 提交），同步后单测复绿；全量复跑 **483/483 全绿（142.2s）**。
- 覆盖率：`scripts/coverage_report.py` 重测写入 `维护记录/覆盖率基线.json`（97 条目标用例全通过，**634 模块／74 覆盖**）；`runbook.md` §11 同步（634/74/560）。
- 过程插曲（如实）：① 批量重写脚本首轮把 `from X import` 的 `import` 后空格吞掉（`importbuild`），AST 全量编译校验 0 语法错误前先由 grep 定位、39 文件批量补空格修复，最终 1466 个 .py 全部可解析；② `round_claim.py next` 在 Python 3.14 下因 git 输出中文路径触发 GBK 解码崩溃，以 `PYTHONUTF8=1` 环境变量绕过领得 R3204（环境问题，未改基准脚本）。

## 观察记录（历史欠账，未扩大范围）

- `architecture.md` §3 L0 行尾部列有 `continuity_ledger`，而 `_layers.py` 登记其为 L1——文档表与登记表的既有不一致（非本批引入，门禁未拦），如实记录。
- `tests/architecture/test_migrated_ui_boundaries.py` 顶层路径空转问题同 R3198 记录，未变。

## 下一步（T10 后续批次）

- infra/ L1 剩余 7 个真实顶层实体：pet_llm(44)、pet_state(45)、storage_maintenance(55)、model_pool(66)、app_logging(81)、file_cache(107)、ui_tokens(149)——中扇出优先 pet_llm/pet_state，file_cache/ui_tokens/app_logging 枢纽随批推进或专轮。
- L4/L3 收官项同前轮：`stage_execution_service`（扇出 50）单独一轮、`writing_api` 随拆分批、`image_agent_runner` 永久除外。
- 门面清除轮需单独授权。
