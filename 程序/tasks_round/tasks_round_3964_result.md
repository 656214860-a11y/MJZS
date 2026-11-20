# R3964 合并轮结果
<!-- round-evidence: {"commit_base": "75068bde", "credential_hits": 0, "evidence_sha256": "8a53e3425b402630", "exit": 0, "failed": 0, "passed": 0, "round": 3964, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`codex/publication-test-fixture-lock` 到 master。
- 说明：修复 test_publication_fsync_budget 偶发红：两条发布测试改为持发布锁摆事务目录（只改测试夹具，产品代码未动）；带干扰复测改前 100 遍过 1 遍、改后各 200 遍全过；定向 20 条绿；全量由合入后的自动全量给出
- 冲突：无（有冲突时本命令中止，不领号）。断言未动。未跑全量。
