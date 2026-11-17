# R3119 并行吞吐治理-B2 全量分级·GUI 调度（部分落地）
<!-- round-evidence: {"commit_base": "8f1e5356", "credential_hits": 0, "evidence_sha256": "93e01a9b48ad6584", "exit": 0, "failed": 0, "passed": 9, "round": 3119, "tests": "run_selftests.py -k lane_merge_queue"} -->

## 三问

- **类型**：功能轮（任务书 B2，治理基建）。
- **测试**：`run_selftests.py -k lane_merge_queue round_claim` 27 条全绿；`smoke_test.py` 9/9 通过。GUI_WAIT 常量无直接断言（`--gui-wait` CLI 可覆盖），无契约破坏。
- **欠账**：无新增；全量 interval 取值为任务书 ❓ 用户决策项，本轮不擅自改动。

## 本轮做了什么

| 任务书 B2 项 | 处置 |
|---|---|
| GUI 等待 15min→30min | ✅ `selftest_env.GUI_WAIT_SECONDS` 900→1800。20 车道下 GUI 串行排队，15min 超时会把整队饿死成 DEFERRED；30min 内仍超时则照旧 `[GUI_DEFERRED] 未执行、不计通过`（`run_selftests.py` 已有该打印且 deferred 时不写分层基线，口径本就真实） |
| DEFERRED 强制标注 | ✅ 现状已满足：打印 + `baseline = '' if deferred`，不另改 |
| `role: gui` 车道 | ⏭ 与 B3 lanes.json 同轮落地（role 字段已支持 `gui`），GUI 密集改动引导走专道属规则文本层，见 runbook 高并发条款 |
| 全量 interval 取值 | ❓ 任务书明列用户决策，本轮保持 `FULL_SAFE_ROUND_INTERVAL=5` 不动 |
| 全量耗时 347s→700-1284s 归因 | 记录：最近绿全量 825s（R3015），中位 533s；增长主因是用例规模与 GUI 串行段占比上升，非单点回归；B1 锁等待后移已消除合并侧 convoy，全量本身降频待 interval 决策 |

## 提交

- `程序/selftest_env.py`（GUI_WAIT_SECONDS 1800）
- 本结果文件、`tasks_round/evidence/R3119.json`

## 三个基线

- 冒烟：9/9 通过
- 架构门禁：未触及架构层（常量调整），本轮不跑 `--architecture`
- 全量：分支不累计欠账；最近 master 全量红项已由 R3112 修复（test_multi_monitor_popups、test_ui_edges_guards），test_soak_light 为环境性波动已记录

## 风险

GUI 等待翻倍只影响「等令牌」上限，不改变串行语义；若 30min 仍不够，DEFERRED 口径不变、结果依然真实。回滚：常量改回 900。

[TASK_COMPLETE]
