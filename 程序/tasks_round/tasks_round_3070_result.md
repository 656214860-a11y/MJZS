# R3070 结果 — 死代码清理轮（结构治理·按报告执行）第 6 批
<!-- round-evidence: {"commit_base": "ce5515a6", "credential_hits": 0, "evidence_sha256": "e90b72fd3d5c0795", "exit": 0, "failed": 0, "passed": 27, "round": 3070, "tests": "run_selftests.py -k coverage_baseline layers"} -->

## 三问

1. **轮次类型**：§3.3 结构治理轮·子场景「按报告执行」。本批删 3 个模块（≤3 上限）。
2. **测试**：`smoke_test.py` 8/8 通过；`test_coverage_baseline`＋`test_layers` 复跑 11/11 通过。
3. **欠账**：同前轮，状态页仅 master 提交不变。

## 本批变更（任务书 A3·orchestrator 死门面第 1 批）

| 动作 | 对象 | 证据 |
|---|---|---|
| 删除 | `stage_animatic_gateways.py`、`stage_asset_gateways.py`、`stage_gate_gateways.py`（各 10 行 `sys.modules` 别名壳） | 任务书 A3：生产/测试/patch/动态引用全零；实体 `orchestrator/` 同名文件 LIVE，由 `stage_execution_service.py` 经包路径 re-export（行 14/33/65） |
| 同步 | `维护记录/覆盖率基线.json` | 移除 3 门面行，modules_total 537→534（covered=0） |
| 同步 | `runbook.md` §11 | 行覆盖 537→534/466→463 |

## 备注

- L3 门面不在分支覆盖率口径（仅 L0/L1），分支基线/下限本批无改动。
- `_layers.py` 未改：登记名经 `entity_file` 解析到 `orchestrator/` 实体。
- 余 6 个 orchestrator 死门面，分两批收尾。
