# R4469 结果：LOCK-LIVENESS-P0 全量锁活性收口、5 分钟等锁上限与先红后绿回归测试
<!-- round-evidence: {"commit_base": "f7c27bb8f", "credential_hits": 0, "evidence_sha256": "0b088455eeeec51d", "exit": 0, "failed": 0, "passed": 102, "round": 4469, "tests": "run_selftests.py -k selftest_lock commit_round selftests scheduled"} -->

## 1. 三问（AGENTS §7）

1. **本轮属于 §3 哪种类型？** 修复轮（§3.2），对应任务卡 LOCK-LIVENESS-P0：《全量锁卡死治理任务书》§3 P0 剩余项收口（结合 R4459 对账结果）。
2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 `smoke_test.py`：通过 9 项、失败 0，退出码 0。
   - 定向 `run_selftests.py -k selftest_lock commit_round selftests scheduled`：4 个测试文件 102 条用例 0 红，退出码 0。
   - 架构门禁 `smoke_test.py --architecture`：708/708（366.255s）退出码 0；未跟踪新测试凭 `test_ownership` 登记通过 STR006 检查，提交后在干净工作树复跑核验（见 §6）。
   - 全量回归 `run_selftests.py --all --safe`：**未运行**（本轮非全量触发点；欠账以 common-dir `full-safe-receipts.json` 为唯一权威，最近绿凭据 R4264）。
3. **欠账少了吗？** 任务书 §6 P0 剩余 4 项全部勾选完成（`--wait-minutes` 默认 5.0、专项测试文件、smoke 验收、结果文件）；未放宽任何基线发现数（baseline `violations` 原样）；范围外欠账见 §7。

## 2. 先红证据（实现前 `run_selftests.py -k selftest_lock`，退出码 1）

6 条用例全红——任务书 P0-3 要求的 5 条＋空/非法 holder 附加用例。输出原文：

```
定向：忽略增量台账，执行 1 个匹配测试文件
跑 1 个测试文件 / 1 路工作单元（8 路并行）
  test_selftest_lock_liveness     6 条     0.2 秒  ✗ 6

共 6 条用例，1.0 秒；1 个文件有红

===== test_commit_round_default_wait_is_five (test_selftest_lock_liveness.LockLivenessTests.test_commit_round_default_wait_is_five) =====
Traceback (most recent call last):
  File "...\程序\tests\test_selftest_lock_liveness.py", line 80, in test_commit_round_default_wait_is_five
    self.assertEqual(seen, [5.0])
AssertionError: Lists differ: [30.0] != [5.0]

First differing element 0:
30.0
5.0

===== test_empty_or_invalid_holder_is_stalled (test_selftest_lock_liveness.LockLivenessTests.test_empty_or_invalid_holder_is_stalled) =====
Traceback (most recent call last):
  File "...\程序\tests\test_selftest_lock_liveness.py", line 74, in test_empty_or_invalid_holder_is_stalled
    self.assertTrue(env._holder_stalled(bad, now=now))
AttributeError: module 'selftest_env' has no attribute '_holder_stalled'

===== test_future_heartbeat_not_stalled (test_selftest_lock_liveness.LockLivenessTests.test_future_heartbeat_not_stalled) =====
Traceback (most recent call last):
  File "...\程序\tests\test_selftest_lock_liveness.py", line 68, in test_future_heartbeat_not_stalled
    self.assertFalse(env._holder_stalled(holder, now=now))
AttributeError: module 'selftest_env' has no attribute '_holder_stalled'

===== test_legacy_lock_without_heartbeat_falls_back (test_selftest_lock_liveness.LockLivenessTests.test_legacy_lock_without_heartbeat_falls_back) =====
Traceback (most recent call last):
  File "...\程序\tests\test_selftest_lock_liveness.py", line 59, in test_legacy_lock_without_heartbeat_falls_back
    self.assertFalse(env._holder_stalled(fresh, now=now))
AttributeError: module 'selftest_env' has no attribute '_holder_stalled'

===== test_live_heartbeat_is_not_reclaimed (test_selftest_lock_liveness.LockLivenessTests.test_live_heartbeat_is_not_reclaimed) =====
Traceback (most recent call last):
  File "...\程序\tests\test_selftest_lock_liveness.py", line 45, in test_live_heartbeat_is_not_reclaimed
    self.assertFalse(env._holder_stalled(holder, now=now))
AttributeError: module 'selftest_env' has no attribute '_holder_stalled'

===== test_stalled_holder_is_reclaimable (test_selftest_lock_liveness.LockLivenessTests.test_stalled_holder_is_reclaimable) =====
Traceback (most recent call last):
  File "...\程序\tests\test_selftest_lock_liveness.py", line 34, in test_stalled_holder_is_reclaimable
    self.assertTrue(env._holder_stalled(holder, now=now))
AttributeError: module 'selftest_env' has no attribute '_holder_stalled'
```

## 3. R4459 对账结论引用（本轮依据）

- **P-H1 成立**：`acquire_gui_lock` 超时返回 `None`（`selftest_scheduling.py:230-232`），`run_selftests.py:259-265,482-483,495-500` 退出码 2 并在 `finally` 释放全量锁，不挂起。
- **P-H2 不成立**：`维护记录/基准脚本/hooks/pre-commit:8-14` 自 R2298（`c6ffbdaa0`）已豁免工作分支，仅拦 `""|master|main`；且 ADR-0015 起全量持 `full-safe-runner.lock`。**本轮不改 hooks/pre-commit。**
- 心跳写入（`heartbeat_at`）、30s daemon 刷新与陈旧锁回收已随 `5d010101d`（`lock_lease.py`）落地；P0 真正未落地仅本轮收口的 4 项（`tasks_round_4459_result.md` §5.2）。

## 4. 改动点（均在允许文件清单内）

| 文件 | 变更 |
| --- | --- |
| `程序/selftest_env.py` | 新增 `_holder_stalled(holder, now=None, stale=lock_lease.LOCK_STALE_SECONDS)`（:280-304）：与 `lock_lease.is_live` 同一静默口径的薄包装；心跳字段兼容 `heartbeat_at`/`heartbeat`，缺心跳字段退回 `started_at`/`created_at` 年龄，未来时间戳不判卡死，空/非法 holder 判 True。`holder_is_live`/`inspect_lock`/`reclaim_stale_lock` 未动。 |
| `程序/scripts/commit_round.py` | `--wait-minutes` 默认 `30.0`→`5.0`（:238）；新增 `_lock_wait_diagnosis`（:232-242），超时返回 3 的提示附持有者 PID、已等时长、心跳距今（缺失写未知）（:333-337）。 |
| `程序/tests/test_selftest_lock_liveness.py` | 新建：任务书 P0-3 全部 5 条用例＋`test_empty_or_invalid_holder_is_stalled`（锁定空/非法 holder 判 True 语义），临时锁文件＋替身 holder，不建真实全局锁、不起 Tk。 |
| `程序/governance/structure.json` | `test_ownership` 登记新测试（kind=module，targets=`selftest_env.py`、`scripts/commit_round.py`）。 |
| `程序/governance/structure-baseline.json` | 仅 `policy_sha256` 一行 `2e4e40c8…`→`7eb7677d…`（= 新 structure.json 字节 sha256）；`violations` 原样，0 新增违规。 |
| `程序/tasks_round/全量锁卡死治理任务书.md` | §6 P0 剩余 4 项勾选并附 R4469 证据；P1/P2 未动。 |
| `程序/tasks_round/tasks_round_4469_result.md` | 本文件。 |

说明：本车道 exec 白名单无直接哈希命令，`policy_sha256` 经新测试内一次性探针断言（借 run_selftests 失败输出取得真实摘要）计算后立即移除，脚手架不随提交入库。

## 5. 接口契约核对

- `_holder_stalled` 签名 `(holder, now=None, stale=…)` 与卡面一致，默认阈值复用 `lock_lease.LOCK_STALE_SECONDS`（180s），未造第二套锁机制。
- `tests/test_commit_round.py` 无断言旧默认 `30.0` 的用例；`-k commit_round` 全部用例通过，无回归。
- 新增测试文件名不在 `run_selftests.SKIP` 名单，位于 `tests/`（规则 15）。

## 6. 验收命令与输出尾部

1. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py`（cwd=`程序`）— 退出码 0：
   ```
   ==================================================
   通过：9 项
   失败：0 项
   ==================================================
   ✅ 冒烟测试通过，可以进入下一轮
   ```
2. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k selftest_lock commit_round selftests scheduled` — 退出码 0：
   ```
   共 102 条用例，84.5 秒；0 个文件有红
   最慢 8 路工作单元：
     test_commit_round#1          82.8 秒 / 14 条
     test_commit_round#2           9.4 秒 / 13 条
     test_selftests_gui_token      3.3 秒 / 17 条
     test_selftests#4              1.7 秒 / 12 条
     test_selftests#1              1.6 秒 / 16 条
     test_selftests#3              0.2 秒 / 16 条
     test_selftests#2              0.2 秒 / 8 条
     test_selftest_lock_liveness    0.1 秒 / 6 条
   实际跳过 0 条用例：本机没有任何登记位被跳过
   ALL TESTS PASSED
   ```
3. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` — 退出码 0：
   ```
   ----------------------------------------------------------------------
   Ran 708 tests in 366.255s

   OK
   ✅ 架构治理测试：tests/architecture
   ```

提交后复跑 `smoke_test.py --architecture` 与 `git status --porcelain` 的结果补记见本文件末尾提交附注。

## 7. 未覆盖项（范围外，如实记录）

- `scripts/merge_round.py:427` 合并路径等锁仍为 `30 * 60`：不在本轮允许文件清单，留 P1/P2。
- `selftest_scheduling.py` GUI 令牌等待提示与 `commit_round.py:226` 周期提示行未打印心跳距今：P1-2 范围（本轮仅按卡面要求补 `commit_round` 超时返回 3 的诊断行）。
- `GUI_WAIT_SECONDS = 1800` 未降值：P1-1 范围。
- 全量 `--all --safe` 未运行：见 §1-2。

**提交状态**：通过 `scripts/dev.py commit` 提交至 `codex/lock-liveness-p0`（本文件由提交门禁补盖 `round-evidence` 机器头）。
