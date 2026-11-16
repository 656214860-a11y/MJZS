# R2930 结果：T10 包化——orchestrator/（L3 编排）批次 13 模块迁移
<!-- round-evidence: {"commit_base": "01cf2f88", "credential_hits": 0, "exit": 0, "failed": 0, "passed": 213, "round": 2930, "tests": "run_selftests.py -k stage_exec stage_gateway stage_publication storyboard_final storyboard_catalog writing_preparation script_skill_report stage_contract handoff_gateway previs animatic"} -->

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；`smoke_test.py --architecture` 架构门禁当轮实测 **470/470 全绿**（随附解释器口径）；定向 23 个测试文件 213 条用例全绿；覆盖率基线重测 **470 模块／70 覆盖**。
3. **欠账少了吗**：是。T10 包化推进第三批：`orchestrator/`（L3）落地 13 个低扇出模块实体＋13 个别名门面。`ui/`（L4）批次、剩余 45 个 L3 模块与顶层前缀族、`app.py`/`pet_cloud.py`/`writing_api.py` 大模块拆分仍是后续批次。

## 本轮交付

| 项 | 内容 |
|---|---|
| `orchestrator/` 实体 | 13 个 L3 模块 `git mv` 入 `orchestrator/`：stage_exec、stage_contract_report、stage_asset_gateways、stage_animatic_gateways、stage_previs_gateways、stage_gate_gateways、stage_handoff_gateways、stage_publication、stage_write_preparation_service、writing_preparation_ledger、script_skill_report、storyboard_final、storyboard_catalog。入选口径：`_layers.py` 登记 L3 且外部扇出最低的天然簇（`stage_*_gateways` 五件＋发布/准备/编目相邻模块，共 13 个；`stage_execution_service` 为重消费者枢纽，留待后续批次）。 |
| 别名门面 ×13 | 顶层同名 `.py` 为 `sys.modules[__name__] = orchestrator.<名>` 别名门面（同 R2921/R2927 口径）：私有名、模块级状态与 `mock.patch('<扁平名>.…')` 补丁面穿透；`ui_plugin_registry` 动态登记与 `contract` 的 `import_module('script_skill_report')` 等扁平名入口不受影响。 |
| 消费方 import | 5 个生产文件改包路径导入（audio_direct_api、stage_execution_service、storyboard_direct_api、storyboard_final_controller、writing_api）；`stage_execution_service` 对五个 gateways 改 `from orchestrator.<名> import (…)` 显式 re-export，扁平名导入面不变；包内互导（animatic→stage_publication/stage_gate_gateways 等）同步改 `orchestrator.` 路径。 |
| `__file__` 锚点 | 本批 13 模块无 `Path(__file__).parent` 根锚用法，无需 `.parents[]` 修正（迁移前扫描 0 命中）。 |
| 日志名保持扁平 | 移动模块内 `logging.getLogger` 显式扁平名，`assertLogs('<扁平名>')` 契约与日志过滤口径不变。 |
| 扫描器适配 | `_scan.py` `stage_execution_source()` 改包感知解析（`orchestrator/<名>.py` 存在则读实体，否则读顶层）——18 条边界门禁红的根因即此；`STAGE_EXECUTION_MODULES` 名单不变。 |
| 测试路径同步 | 6 个测试文件实体路径改 `orchestrator/<名>.py`：4 个架构边界测试（asset_plan_publication、final_bundle、project_context、structured_script_write）＋2 个普通测试（stage_wiring、storyboard_final_scope）；`test_atomic_write_boundary` 等 basename 键登记表不改（registry_key 口径即 basename）。 |
| 棘轮台账 | `架构统一基数.json` 第四项 4 个 file 字段改 `orchestrator/<名>.py`（relpath 口径，exempt 处置不变）。 |
| 基线与文档 | `覆盖率基线.json` 重测 **470 模块／70 覆盖**（+13 实体＋`orchestrator/__init__.py`）；`runbook.md` §11 数字同步（456/69/387→470/70/400）；`architecture.md` 目录树加 `orchestrator/`；`PROJECT_MAP.md`（stage_exec 条目）、`distribution_manifest.md` glob 同步。 |

## 验证记录

- `smoke_test.py`（随附解释器）：8/8 通过。
- `smoke_test.py --architecture`（随附解释器）：首轮 18 红（`stage_execution_source()` 读门面＋台账/runbook 数字未同步），修复后复跑 **470/470 全绿**（当轮实测）。
- 定向：`run_selftests.py -k <13 模块相关关键词>` → 23 个测试文件 213 条用例 0 红。
- 导入冒烟：`orchestrator.*` 实体、扁平门面、`stage_execution_service`/`writing_api` 重消费者全部可导入，无循环。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按 `full-safe-receipts.json` 凭据口径执行）。

## 过程损耗（如实）

- 首轮架构门禁 18 红全部定位为「门面替身被当实体读」同类问题：`stage_execution_source()` 拼接读顶层 `.py`（现为 5 行门面），修复为包感知解析后一处归零；台账 relpath 与 runbook §11 数字按 R2927 同法同步。
- `run_selftests.py` 不接受测试文件路径参数（`nargs="*"` 语义），定向复跑改用 `python -m unittest <模块列表>`，53 条先行验证后再跑全门禁。

## 下一步（T10 后续批次）

- `ui/`（L4）批次与剩余 45 个 L3 模块（`stage_execution_service` 等重消费者枢纽）、顶层前缀族，逐批同法迁移；本批验证的适配点（`stage_execution_source` 包感知、台账双口径、日志名冻结、门面别名）直接复用。
- `app.py`、`pet_cloud.py`、`writing_api.py` 大模块只读拆分方案先行（任务书 T10 前置要求）。
