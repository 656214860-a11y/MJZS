# R2631 结果：修复 test_selftests 第三处 _recent_swallowed 长度断言（合并阻断）
<!-- round-evidence: {"commit_base": "e46f8bc9", "credential_hits": 0, "evidence_sha256": "212710e80f4753cc", "exit": 0, "failed": 0, "passed": 61, "round": 2631, "tests": "run_selftests.py -k selftests"} -->

1. 轮次类型：修复轮（合并阻断修复，最小改动对齐 R2626 同型修法）。
2. 测试：`-k selftests` 全绿；冒烟与架构随 R2628 同批验证。
3. 欠账：master 全量红的最后一个已知站点已清除，合并通道恢复前置。

## 根因与修法

- `test_cleanup_failure_leaves_swallowed_trace` 用 `len > before` 断言；
  `_recent_swallowed` 为 deque(maxlen=20)，全量运行进程内满 20 后必败，
  与 R2626 修的另两处同型。
- 修法同 R2626：断言前先 `_recent_swallowed.clear()`。
- 全仓 grep 复核：其余 `_recent_swallowed` 长度断言均已有 clear 保护。
