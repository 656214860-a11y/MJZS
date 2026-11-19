# R3804 结果：G-0/G-1 门控复核（K1–K18 推进前置核对）
<!-- round-evidence: {"commit_base": "0d97e931", "credential_hits": 0, "evidence_sha256": "ec2c41979e83ebaf", "exit": 0, "failed": 0, "passed": 0, "round": 3804, "tests": "docs-only"} -->

## 三问

- 轮型：§3.10 验证／基线轮（门控复核，docs-only；同 R3384/R3465/R3537/R3687 先例）。
- 测试：不跑（无 `.py` 改动；核对命令为 `git`／`taskbook_closure.validate()`）。
- 欠账：无代码改动；任务书头部状态行与 E24 明细已按 master `2c0dce41` 刷新。

## 背景

用户指令「调度 L0 宪法车道推进 K1–K18」。按 §6.1 依赖图，K1 之后全部 K 轮（K3–K23，除已完成的 K2/K8/K9）均传递依赖 K1；K1 前置含 G-1。本轮复核 G-0/G-1 当前状态，判定可执行面。

## 门核对（master = `2c0dce41`，R3784）

| 门 | 结论 | 证据 |
| --- | --- | --- |
| G-0 | **仍满足** | `git merge-base --is-ancestor 9a611353 master` = yes；`taskbook_closure.validate()` 返回 `[]` |
| G-1 | **未满足** | 命中 4 个点名文件的 `codex/foundation-*` 分支 **15→16**（新增 `foundation-next`，4 文件全中、ahead 11、tip R3703）；`resume` ahead 8→11、tip R3599→R3703；round2–5-history、pre-sync-squash 支线 tip 推进至 2026-11-19，地基车道仍活跃 |

命中判定命令：`git -c core.quotepath=false diff --name-only master...codex/foundation-*` 按 `contract/platform_tools.py`、`contract/service_contract.py`、`contract/workflow_context_budget.py`、`tests/architecture/test_dependency_whitelist.py` 过滤 → 16 支（明细已更新任务书 E24 表）。

## 可执行面判定

- **K1–K18 无一可开工**：依赖图硬边 `G-1 → K1`、`K1 → K3/K5/K6/K7/K16/K20`、`K3 → K4 → K5/K6/K15`、`K6/K9 → K11 系`、`K11 → K18 → K19` 使全部剩余轮次传递依赖 G-1。任务书头部状态行同口径：「K1 及全部下游轮次继续阻塞于 G-1」。
- G-1 解除条件（地基分支合入 master 或明确放弃）属他人车道：§3.4 明令「需要合并他人车道的分支，或代填他人的验收勾选」须 `[TASK_BLOCKED]`；地基车道今日仍有提交（foundation-next/resume tip R3703），非放弃状态。
- 附带观察：`foundation-config-project-profile`（ahead 4）、`foundation-config-write-safety`（ahead 1）命中 `infra/project_settings.py`——属 L1 车道 G-B 文件集，不计入本门。

## 结论

- 本车道可执行项仅剩门控复核类 docs-only 轮；K1–K18 全部阻塞于 G-1，解除需地基车道交付或用户明确裁决分支处置。
- 已同步刷新任务书头部状态行与 E24 分支矩阵，供下一执行会话直接续用。

## 验证

- 门核对命令输出如上（docs-only，无测试可跑）。
- 三个基线：冒烟／架构门禁／全量均未运行（无代码改动）。

## 提交

- （提交后回填）
