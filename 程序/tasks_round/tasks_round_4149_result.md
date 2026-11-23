# R4149 结果：retry 与 failures 统一含 MISSING（FIX-AUD-SKILL-RETRY）
<!-- round-evidence: {"commit_base": "3383684c", "credential_hits": 0, "evidence_sha256": "e82c034e3f012e69", "exit": 0, "failed": 0, "passed": 15, "round": 4149, "tests": "run_selftests.py -k skill_orchestrator stage_execution_service"} -->

## 开头三问

（一）本轮类型：修复轮。任务卡 FIX-AUD-SKILL-RETRY（队列 169）；缺陷 AUD-SKILL D9——`stage_exec.failures` 含 MISSING，`SkillOrchestrator.retry` 只看 `run['failed']`（仅 FAILED）。车道 `codex/fix-aud-skill-retry`，基准 `3383684c`。

（二）测试与三个基线：`run_selftests.py -k skill_orchestrator stage_execution_service` 改前 15 条里 1 条红，改后 15 条全过（原 14 + 新增 1），退出码 0。架构门禁初版因 Orchestrator 类行数超棘轮红 1；把 `retryable_skills` 提到模块级后 700 条全过，退出码 0。默认冒烟与全量未跑。

（三）欠账：`run['failed']` 仍只记 FAILED（避免动 `ok` 语义与既有断言）；重试列表改走 `retryable_skills`。`stage_exec.py` 本轮未改（failures 口径本已正确）。

## 缺陷复现

构造含 MISSING＋FAILED 的 Run，`failures()` 得到两名，`retry` 的 `retried` 只有 FAILED——改前 `AssertionError: Lists differ: ['boom-skill'] != ['ghost-skill', 'boom-skill']`。

## 改了哪些文件

- `orchestrator/skill_orchestrator.py`：新增模块级 `retryable_skills`；`retry` 用它代替只读 `run['failed']`。
- `tests/test_skill_orchestrator_completion.py`：新增 `test_retry_includes_missing_listed_by_failures`。
- 本结果文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| 开工三查 | 干净；`3383684c`；`codex/fix-aud-skill-retry` |
| 定向（改前） | 退出码 1；15 条，1 红 |
| 定向（改后） | 退出码 0；15 条；`ALL TESTS PASSED` |
| `smoke_test.py --architecture` | 退出码 0；`Ran 700 tests in 226.048s`；`OK` |
| `scripts\dev.py claim` | 领到 4149 |
