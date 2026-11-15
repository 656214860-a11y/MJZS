# R2564 结果
<!-- round-evidence: {"commit_base": "dee15127", "credential_hits": 0, "evidence_sha256": "3a62a596eb310fde", "exit": 0, "failed": 0, "passed": 7, "round": 2564, "tests": "run_selftests.py -k merge_round"} -->

1. 轮次类型：修复轮（合并工具并发缺陷）。
2. 测试：`tests.test_merge_round` 7 条全绿（新增 3 条临时仓库用例）；默认冒烟 8/8。断言未动。
3. 欠账：无新增。

## 起因

合并 `codex/wip-R2559` 时与另一会话的合并轮撞车：对方 `merge --no-commit` 已建 MERGE_HEAD，本命令的 `git merge` 报 “MERGE_HEAD exists” 失败后，旧代码无条件 `merge --abort`，把对方的合并现场清掉了（对方随后以 R2561 重试成功，R2560 烧号）。这是批次 1.3 引入的回归：失败路径没有区分「自己的冲突合并」和「别人的合并现场」。

## 改动

- `scripts/merge_round.py`：
  - 新增 `merge_in_progress()`／`merge_head_is(branch)`／`cleanup_failed_merge(branch)`；
  - 开头预检：MERGE_HEAD 存在直接拒绝运行（return 2），不再进入等锁与合并；
  - 失败清理只在 `MERGE_HEAD` 解析值等于本次分支头时才 `merge --abort`，否则原样保留现场并报错。
- `tests/test_merge_round.py`：临时仓库造「feature 的冲突合并现场」，验证 `merge_in_progress`／`merge_head_is` 判定，以及 `cleanup_failed_merge('master')` 返回 `foreign` 且不动现场、`cleanup_failed_merge('feature')` 返回 `conflict` 且还原。

## 残余风险

预检到 `git merge` 之间仍有毫秒级竞态；但失败清理已按 MERGE_HEAD 指向判定归属，只误伤「同一分支被两个会话同时合并」的极端情形。旧版本 merge_round（master 当前所跑）仍有该缺陷，本修复随本分支合入后才对全员生效。
