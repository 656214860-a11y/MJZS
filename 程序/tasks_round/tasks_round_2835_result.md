# R2835 结果：T10 批次2——pet_bus 迁入 contract/（阶段顺序与事件总线权威模块）
<!-- round-evidence: {"commit_base": "a4b17da5", "credential_hits": 0, "evidence_sha256": "68ffbb23d3cc288f", "exit": 0, "failed": 0, "passed": 155, "round": 2835, "tests": "run_selftests.py -k pet_bus broadcaster stage_flow pet_error_log coverage_baseline static_hygiene layers circular size_ratchet complexity service_return structured_script gate_selfaudit app_metadata facade"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮（§3.3，T10 批次 2 收尾之一：`pet_bus`——`pet_bus.STAGES`／`STAGE_NAMES` 阶段顺序唯一权威、`emit_safe()` 事件唯一安全发送器、`ErrorLog` 有界错误表——迁入 `contract/`）。分支 `codex/wip-R2835`（T10 工作树，叠于 R2832）。队列：无对应 ID。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过；`contract.pet_bus` 实测 `STAGES` 13 阶段、`emit_safe` 可用、门面与实体同一函数对象。
   - `smoke_test.py --architecture` 466 条：pet_bus 相关 2 项红（coverage 基线未刷新、`test_pet_error_log_boundary` 豁免按全路径失配）修复后复跑；余 3 红 1 错为工作树固有环境欠账（同 R2832 记录）。
   - 定向 `run_selftests.py -k pet_bus broadcaster emit_safe stage_flow` **87 条全绿**（4.1 秒）。
   - `coverage_report.py` 97 条全过，基线 **401→402** 模块；`runbook.md` §11 同步。
   - 全量 `--all --safe`：未跑（分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；contract/ 扩到 29 个 L0 模块，批次 2 仅剩 platform_tools。

## 交付

- `git mv pet_bus.py → contract/pet_bus.py`＋顶层显式再导出门面；61 个生产文件 import 改写为 `contract.pet_bus`（含 `import ... as pet_bus` 别名保持 `pet_bus.X` 访问不变）。
- `tests/architecture/test_pet_error_log_boundary.py`：ALLOWED 豁免键由全路径改 basename（`contract/pet_bus.py` 与门面同豁免 `Bus` 类），断言意图不变（§2.4 契约同步）。
- `维护记录/覆盖率基线.json`、`runbook.md` §11、`architecture.md` contract/ 计数同步。

## 机制记录

- pet_bus 仅依赖 stdlib＋`agent.core.read_json`，无 contract 内互引、无动态字符串引用，循环风险为零。
- `production_runtime_files()` 递归口径本就覆盖包目录——`pet_*` 棘轮测试先天能看到实体，暴露的是豁免键口径问题而非扫描盲区。

## 环境欠账（与本 diff 无关）

同 R2832：`基准历史.json`（gitignore 运行文件缺）、`project_status.md` 分支轮次滞后、技能包未跟踪内容缺失（`screenplay-gate-engine.md`／`编剧技能集`／`剧本锻造`）。

## 未覆盖／下一步

- contract/ 余 platform_tools（60 引用，纯 stdlib 工具集，下一轮）。
- 批次 3–6：infra/domain/orchestrator/ui 各包需先在 `distribution_manifest.md` 登记 `程序/<包>/**`。
