# R3961 合并轮结果
<!-- round-evidence: {"commit_base": "c6ae9f72", "credential_hits": 0, "evidence_sha256": "7e7983bdfd9f253e", "exit": 0, "failed": 0, "passed": 0, "round": 3961, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`codex/git-lock-g2-precise-overlap` 到 master。
- 说明：提交门禁改为按真实冲突判断（锁任务书 G2）：只在与活跃车道有新冲突或同名新增时拒绝；新测试文件已登记归属；定向 75 条绿；全量由合入后的自动全量给出
- 冲突：无（有冲突时本命令中止，不领号）。断言未动。未跑全量。
