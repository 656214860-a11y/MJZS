# R3631 结果文件 — 稳定旧版发布事务恢复夹具
<!-- round-evidence: {"commit_base": "f82f40f3", "credential_hits": 0, "evidence_sha256": "438b138647c3eb50", "exit": 0, "failed": 0, "passed": 17, "round": 3631, "tests": "run_selftests.py -k publication_fsync_budget publication_recovery renew_concurrency"} -->

## 三问

1. 本轮为验收修复轮。R3619 干净检出全量 9049 条零失败，正式主干入口随后执行相同程序树时，旧版 pending 发布日志恢复用例出现一项间歇失败。单文件在同一 CI 检出独立复验 7/7。
2. 测试夹具在发布锁内落盘，committed 和 pending 使用独立目录。发布恢复、同步预算和续签并发定向 17/17。正式全量凭据待主干复验。
3. 保留旧版 committed 不回滚、pending 恢复旧内容和清理事务目录的原断言。本轮只调整测试准备，无产品源码变更。
