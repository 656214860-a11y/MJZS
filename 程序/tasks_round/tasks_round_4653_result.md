# R4653 首帧从回收站恢复时被其他事务的旧备份占用阻断
<!-- round-evidence: {"commit_base": "e3898a897", "credential_hits": 0, "evidence_sha256": "c55a3cd91f932683", "exit": 0, "failed": 0, "passed": 32, "round": 4653, "tests": "run_selftests.py -k test_keyframe_lifecycle_service test_publication_fsync_budget test_publication_recovery test_keyframe_restore_boundary"} -->

- 类型为执行轮（缺陷修复）。做定向并发复现和相关回归，未重跑全量。三项基线以合并门禁为准。
- 修复一处可复现的跨项目干扰。R4628 原始日志只有恢复返回 False，无法追认当时的占用者。

R4628 的非 GUI 阶段使用 8 个工作进程。回放相邻分片 647 条通过，重复并发运行首帧生命周期 1056 条通过。无额外占用时，并发本身不足以解释故障。

定向用例在独立临时事务目录完成另一次真实发布，同时保留旧备份的 Windows 读句柄。恢复首帧时，原实现再次清理已提交事务，清理失败经清单读取转换为“恢复清单无法读取”。修复前同一组 8 个进程共 96 条，8 个占用用例均失败。修复后同组 96 条全部通过。

发布层仅在确认日志缺失时推迟清理。持有句柄期间核验还原图片及磁盘索引，释放后核验残留回收与其他事务的提交结果。原恢复断言保留服务返回的原因和详情，以便与后续现场对照。
