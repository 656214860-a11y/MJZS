# R4655 合并轮结果
<!-- round-evidence: {"commit_base": "e3898a897", "credential_hits": 0, "evidence_sha256": "97208a248106e46d", "exit": 0, "failed": 0, "passed": 0, "round": 4655, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`codex/keyframe-restore-concurrency` 到 master。
- 说明：修复已提交事务备份占用阻断首帧回收恢复，8 进程定向验证通过
- 冲突：无（有冲突时本命令中止，不领号）。断言未动。未跑全量。
