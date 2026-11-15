# 轮次 2632 结果

## 三问

- 类型：§3.2 修复轮（合并阻断级·测试环境适配，R2626 同类补丁的第三处漏网点）
- 测试：跑了——`unittest tests.test_selftests.WorkerCleanupTests` 3/3 绿
- 三个基线：冒烟未跑（单行隔离补丁）；架构门禁未跑；全量未跑
- `project_status.md` 欠账：不少——解锁修复

## 改动

- `tests/test_selftests.py`：`test_cleanup_failure_leaves_swallowed_trace` 断言增长前
  加 `app_logging._recent_swallowed.clear()`。环形缓冲满 20 时「len > before」必败；
  自动全量在 b061746f 上仅剩此红（test_auto_full_safe／test_swallowed_cleanup 的
  同款问题已由 R2626 修复，此处是同模式第三处）。
