# R4318 · AST-VERSION-1：资产版本管理与历史版本追踪
<!-- round-evidence: {"commit_base": "0815d266f", "credential_hits": 0, "evidence_sha256": "ac9be492940ee42a", "exit": 0, "failed": 0, "passed": 19, "round": 4318, "tests": "run_selftests.py -k asset_versions"} -->

## 开头三问

- （一）本轮类型：功能轮（AGENTS.md §3.1），车道 `codex/ast-version-1`，基准 `master` `0815d266f`。
- （二）测试跑了吗、三个基线：定向 `run_selftests.py -k test_asset_versions coverage_baseline service_return_contract` 全绿（0 红）；`scripts/coverage_report.py` 15 组定向目标全绿并刷新 `维护记录/覆盖率基线.json`（133/682）。默认冒烟与完整架构门禁由合入出口 CI 覆盖；全量回归未跑（以 `full-safe-receipts.json` 为准）。
- （三）欠账少了吗：未新增欠账。

## 改动文件

- `程序/domain/asset_versions.py`：新增资产版本管理领域模块。
- `程序/asset_reference_images.py`、`程序/domain/asset_batch_service.py`、`程序/domain/asset_plan.py`：接入资产版本记录与引用。
- `程序/docs/specs/09_资产数据生命周期.md`、`程序/docs/stages/S05_资产管理.md`：同步资产版本规格与阶段文档。
- `程序/tests/test_asset_versions.py`：新增 19 条单元测试。
- `程序/tests/architecture/_layers.py`、`程序/维护记录/架构统一基数.json`、`程序/维护记录/覆盖率基线.json`、`程序/runbook.md`：登记 `asset_versions` 层级与覆盖率基线（681 → 682）。
- `程序/tasks_round/tasks_round_4318_result.md`：本文件。

## 验证记录

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `scripts/coverage_report.py <15 targets> --json 维护记录/覆盖率基线.json` | 0 | 模块被覆盖 133/682，目标用例全通过 |
| `run_selftests.py -k test_asset_versions coverage_baseline service_return_contract` | 0 | 全绿，0 红 |
