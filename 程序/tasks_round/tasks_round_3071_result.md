# R3071 结果 — 死代码清理轮（结构治理·按报告执行）第 7 批
<!-- round-evidence: {"commit_base": "1eced6d9", "credential_hits": 0, "evidence_sha256": "ed3507e4724b58e6", "exit": 0, "failed": 0, "passed": 27, "round": 3071, "tests": "run_selftests.py -k coverage_baseline layers"} -->

## 三问

1. **轮次类型**：§3.3 结构治理轮·子场景「按报告执行」。本批删 3 个模块（≤3 上限）。
2. **测试**：`smoke_test.py` 8/8 通过；`test_coverage_baseline`＋`test_layers` 复跑 11/11 通过。
3. **欠账**：同前轮，状态页仅 master 提交不变。

## 本批变更（任务书 A3·orchestrator 死门面第 2 批）

| 动作 | 对象 | 证据 |
|---|---|---|
| 删除 | `stage_handoff_gateways.py`、`stage_previs_gateways.py`、`stage_publication.py`（各 10 行别名壳） | 任务书 A3：引用全零；实体 LIVE（`stage_execution_service.py` 行 43/80/98 经包路径 re-export；`orchestrator/audio_direct_api.py:132`、`stage_animatic_gateways.py` 实体内部经包路径用 `stage_publication`） |
| 同步 | `维护记录/覆盖率基线.json` | 移除 3 门面行，modules_total 534→531（covered=0） |
| 同步 | `runbook.md` §11 | 行覆盖 534→531/463→460 |

## 备注

- L3 门面不在分支覆盖率口径；`_layers.py` 未改（`entity_file` 解析到 orchestrator 实体）。
- 余 3 个死门面（stage_write_preparation_service、white_model_persistence_controller、writing_preparation_ledger），下一批收尾。
