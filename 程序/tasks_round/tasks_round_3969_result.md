# R3969 合并轮结果
<!-- round-evidence: {"commit_base": "05d8ec19", "credential_hits": 0, "evidence_sha256": "23fc05d2687c06c0", "exit": 0, "failed": 0, "passed": 0, "round": 3969, "tests": "merge-ci-exit"} -->

- 轮次类型：合并轮。
- 合入：`codex/full-safe-red-breakdown` 到 master。
- 说明：统计报告新增全量红灯归因一节：按同一提交红绿不一识别偶发，把红的全量分成只有偶发、含持续红、未定、没有失败文件名四类，并剔除全量历史里的 182 行样例记录（有效全量 115 次：绿 20、红 95，其中只有偶发 9 次、含持续红 71 次）；定向 15 条绿、冒烟 9 项过；全量未跑，按欠账规则由后台补跑
- 冲突：无（有冲突时本命令中止，不领号）。断言未动。未跑全量。
