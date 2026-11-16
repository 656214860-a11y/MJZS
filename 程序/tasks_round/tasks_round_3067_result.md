# R3067 结果 — 死代码清理轮（结构治理·按报告执行）第 4 批
<!-- round-evidence: {"commit_base": "a15d8705", "credential_hits": 0, "evidence_sha256": "834523f0e4cbf408", "exit": 0, "failed": 0, "passed": 31, "round": 3067, "tests": "run_selftests.py -k coverage_baseline branch_coverage_floor layers"} -->

## 三问

1. **轮次类型**：§3.3 结构治理轮·子场景「按报告执行」。本批删 3 个模块（≤3 上限）。轮次号 3067（3066 被并行车道领走，跨树唯一由 round_claim 保证）。
2. **测试**：`smoke_test.py` 8/8 通过；`test_coverage_baseline`＋`test_branch_coverage_floor`＋`test_layers` 复跑 15/15 通过。
3. **欠账**：同前轮，状态页仅 master 提交不变。

## 本批变更（任务书 A3·T10 死门面第 1 批：contract L0）

| 动作 | 对象 | 证据 |
|---|---|---|
| 删除 | `script_brief.py`、`model_protocol.py`、`pet_settings_contract.py`（各约 10 行别名壳） | 任务书 A3：生产/测试/patch/动态引用全零；实体 `contract/script_brief.py`、`contract/model_protocol.py`、`contract/pet_settings_contract.py` 均 LIVE（`script_contract.py`、`model_secrets.py`、`pet_settings_ui.py`/`pet_ui.py`/`pet_ui_support.py` 经包路径导入） |
| 同步 | `tests/architecture/test_layers.py` | 僵尸登记名判定由 `ROOT/<name>.py` 改为 `entity_file(name)`（T10 包实体优先）——门面删除后登记名仍解析到包实体，分层分类不丢；该修正是收紧而非放宽（无实体处仍判僵尸） |
| 同步 | `维护记录/覆盖率基线.json` | 移除 3 个门面行，modules_total 543→540（covered=0） |
| 同步 | `维护记录/分支覆盖率基线.json`＋`分支覆盖率下限.json` | L0/L1 口径移除 3 行/3 下限，modules_total 80→77，points_total 2157→2153、points_covered 1050→1047（script_brief 实测 3/4 点随文件删除） |
| 同步 | `runbook.md` §11 | 行覆盖 543→540/472→469；分支覆盖 80→77 个顶层模块 |

## 备注

- `_layers.py` 本批**未改**：三个登记名经 `entity_file` 解析到 `contract/` 实体，分层分类保持有效——这正是门面可安全删除的前提。
- 剩余 12 个 T10 死门面分四批（每批 3 个）：orchestrator 网关簇与 infra/domain/contract 门面混合排期。
