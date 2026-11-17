# R3064 结果 — 死代码清理轮（结构治理·按报告执行）第 2 批
<!-- round-evidence: {"commit_base": "09e8cd8f", "credential_hits": 0, "evidence_sha256": "cefb7738983e2f15", "exit": 0, "failed": 0, "passed": 47, "round": 3064, "tests": "run_selftests.py -k stage_layout coverage_baseline layers"} -->

## 三问

1. **轮次类型**：§3.3 结构治理轮·子场景「按报告执行」。本批删 2 个模块（≤3 上限）。
2. **测试**：`smoke_test.py` 8/8 通过；`run_selftests.py -k stage_layout` 20/20 通过；覆盖率基线/分层门禁沿用 R3063 口径，本批同步后 `test_coverage_baseline`＋`test_layers` 复跑通过（unittest 直跑 12 项中仅 test_stage_layout 收集路径报 skip_reasons，项目 runner 下全绿）。
3. **欠账**：同 R3063，状态页仅 master 提交不变。

## 本批变更（任务书 A2·契约报表簇）

| 动作 | 对象 | 证据 |
|---|---|---|
| 删除 | `orchestrator/stage_contract_report.py`（20 行）＋`stage_contract_report.py`（10 行门面） | 任务书 A2：实体 prod_in=1 仅门面；门面仅被 test_stage_layout 平铺导入；`contract_rows()` 无任何 UI/报告调用方 |
| 同步 | `tests/test_stage_layout.py` | 移除 `from stage_contract_report import contract_rows` 与 `test_contract_rows_pair_stages_with_gates_and_docs` 用例（§2.4：被测对象删除，断言未弱化） |
| 同步 | `tests/architecture/_layers.py` | L3 移除 `stage_contract_report` 登记名 |
| 同步 | `维护记录/覆盖率基线.json` | 文本级移除两模块行，modules_total 547→545（两行 covered=0，modules_covered 不变） |
| 同步 | `runbook.md` §11 | 基线数字 547→545、476→474 |

## 备注

- `contract_rows` 全仓仅剩 `domain/confirm_gates.py` docstring 一处散文提及（"stage_layout.contract_rows"），为陈旧注释不影响运行，记录备查不改。
- 下一批 R3065：storyboard_catalog 兼容簇（同构 2 模块）。
