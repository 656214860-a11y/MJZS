# R3129 B1 修复：合并候选 CI 期间轮次连续性检查结构性豁免+领号后复核
<!-- round-evidence: {"commit_base": "76020fac", "credential_hits": 0, "evidence_sha256": "bbc2565a48aeaa92", "exit": 0, "failed": 0, "passed": 9, "round": 3129, "tests": "run_selftests.py -k merge_round"} -->

## 三问

- **类型**：修复轮（R3121 合并轮 exit-CI 架构门禁红 → 根因修复）。
- **测试**：`run_selftests.py -k merge_round` 9/9 绿；`test_round_baselines` 合并态跳过分支已就位（分支上下文 status 旧属预期，不验收）。
- **欠账**：无新增；本轮闭环 R3120/R3125 合并被拦欠账。

## 根因

B1 把领号移到 exit-CI 之后（不烧号），但 `test_round_number_continuous` 要求「当前轮次==最新结果+1」——合并候选树在 CI 时点状态页尚未抬头、分支自带更新结果文件，**结构上不可能成立**，任何带结果文件的分支合并都会被架构门禁拦下。两次合并失败均未领号、现场自动还原（B1 语义实测正确）。

## 修复（两半）

1. `tests/architecture/test_round_baselines.py`：`MERGE_HEAD` 存在（合并进行中）时 `test_round_number_continuous` skipTest——不变量在合并候选期被定义性挂起，非合并树不受影响。
2. `scripts/merge_round.py`：新增 `continuity_gap()`；领号写状态页+结果文件后、`commit_round` 提交前复核「当前轮次==最新结果+1」，不满足则删未跟踪结果文件+`cleanup_failed_merge` 还原本分支现场、return 4。领号公式保证 N>所有既有结果号，复核为兜底防线。

## 提交

- `程序/scripts/merge_round.py`
- `程序/tests/architecture/test_round_baselines.py`
- 本结果文件、`tasks_round/evidence/R3129.json`

## 三个基线

- 冒烟：本轮未跑全量冒烟（治理脚本+架构测试改动）；`test_merge_round` 9/9、定向架构测试绿
- 架构门禁：被测对象即门禁本体，分支上下文预期红已注明；合并候选态验证待下次合并实测
- 全量：分支不累计欠账

## 风险

合并候选期跳过该检查的窗口＝merge --no-commit→commit 之间；窗口内若有其他会话读该测试会得到 skip 而非 FAIL——可接受，因为该不变量只在提交后才有定义。回滚：还原两文件。

[TASK_COMPLETE]
