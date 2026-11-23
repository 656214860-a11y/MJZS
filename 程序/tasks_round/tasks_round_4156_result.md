# R4156 FIX-BOOT-READY-LATE
<!-- round-evidence: {"commit_base": "7684a7e7", "credential_hits": 0, "evidence_sha256": "0616d0969830caa8", "exit": 0, "failed": 0, "passed": 98, "round": 4156, "tests": "run_selftests.py -k test_startup_selfcheck test_desktop_startup_perf test_login_gate desktop.py ui/desktop_automation_tick.py infra/diagnostic_capture.py tests/test_startup_selfcheck.py docs/specs/02_接口与详细设计.md tasks_round/tasks_round_4156_result.md"} -->

## 三问

1. 类型：修复轮（有意契约变更：崩溃预算 READY 时机后移，DES-APP-06）。
2. 测试：定向 `-k startup_selfcheck desktop_startup_perf login_gate` 先红后绿（改前 98 条／8 红 → 改后 98 条／0 红，EXIT=0）；`smoke_test.py --architecture` 700 条 OK，EXIT=0。默认冒烟未跑（卡面禁止）。`--affected desktop diagnostic_capture desktop_automation_tick` 在 900 秒门禁超时（选出 111 个模块串行），非断言失败。
3. 欠账：真机反复崩溃弹二选一的端到端未实测；`--affected` 完整绿未拿到（超时）。

## 缺陷复现（改前红）

新用例 `StartupReadyLateTests` 共 9 条；改前产品仍在 `__init__` 末尾 `record_startup_ready`，settle／兜底／登录闸守卫未实现 → **8 条红**（`test_death_before_ready_still_counts_toward_safe_start` 原状态机已绿）：

- `test_resume_tick_clears_attempt_after_settle`：settle 后 `attempt_at` 仍在
- `test_arm_without_login_keeps_attempt_until_settle` 等 6 条：缺 `_arm_startup_ready_guard`
- `test_ready_fallback_ms_is_sixty_seconds`：缺 `READY_FALLBACK_MS`

命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k startup_selfcheck desktop_startup_perf login_gate`  
输出摘要：`共 98 条用例，27.1 秒；1 个文件有红`／`### test_startup_selfcheck（8 条红）`

## 改动

| 文件 | 要点 |
| --- | --- |
| `程序/docs/specs/02_接口与详细设计.md` | 新增 §4.4 REQ-APP-06／DES-APP-06 |
| `程序/desktop.py` | 删 `__init__` 末尾 READY；初始化 `_startup_ready_fallback_id`；改调 `_arm_startup_ready_guard()` |
| `程序/ui/desktop_automation_tick.py` | `_arm_startup_ready_guard`／`_startup_ready_fallback`／`_cancel_startup_ready_fallback`；settle 后清零并取消兜底 |
| `程序/infra/diagnostic_capture.py` | `READY_FALLBACK_MS=60000`；更新 `record_startup_ready` 文档串 |
| `程序/tests/test_startup_selfcheck.py` | `StartupReadyLateTests` 9 条（无真实 Desktop／Tk） |

`test_desktop_startup_perf` 既有首帧时序断言未改，改后仍绿。

## 改后验收

1. 同上 `-k`：`共 98 条用例…；0 个文件有红`／`ALL TESTS PASSED`，EXIT=0
2. `smoke_test.py --architecture`：`Ran 700 tests in 260.240s`／`OK`，EXIT=0
3. `smoke_test.py --affected …`：`900 秒 → 超时`，EXIT=1（门禁墙钟，非用例红）

## 未验证

- 真机连续崩溃至安全模式二选一的端到端
- `--affected` 全量定向在 900 秒内跑完

## 回滚

`git revert` 本轮提交。
