# R3007 合并轮结果
<!-- round-evidence: {"commit_base": "5efaee2e", "credential_hits": 0, "evidence_sha256": "09c7a250d71f9744", "exit": 0, "failed": 0, "passed": 0, "round": 3007, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`gilded-darwin` 到 master。
- 说明：R2995 修复轮——合并门禁放行同HEAD红冷却解死锁（auto_full_safe.current_cooling唯一判定，'time'/BLOCKED仍拦）+test_auto_full_safe历史写入mock收口
- 冲突：无（有冲突时本命令中止，不领号）。断言未动。未跑全量。
