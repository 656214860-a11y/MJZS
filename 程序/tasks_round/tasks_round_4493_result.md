# tasks_round_4493_result — REF-L1-1 修复 infra/executors.py 三处并发缺陷
<!-- round-evidence: {"commit_base": "377cd201a", "credential_hits": 0, "evidence_sha256": "531f045afad95cec", "exit": 0, "failed": 0, "passed": 40, "round": 4493, "tests": "run_selftests.py -k executors force_quit"} -->

- 本轮属于 §3.2 修复轮（REF-L1-1 卡面：L0-L5 深审已证实的 3 处并发漏洞，先红后绿最小修复，只改根因模块）。
- 测试跑了吗、三个基线过了吗：跑了。卡面两条验收命令退出码均 0——`run_selftests.py -k executors force_quit`（40 条 0 红）；`smoke_test.py --architecture`（708 条 OK）。默认冒烟基线未单跑（卡面未要求）；全量 `--all --safe` 未跑（分支车道不累计）。
- 欠账少了吗：修复 3 处已证实并发缺陷，既有 executors／force_quit 契约全部保持；无新增欠账。

## 先红原文（改码前实测，exit 1）

```
test_executors                19 条    11.9 秒  ✗ 3
共 40 条用例，13.7 秒；1 个文件有红

### test_executors（3 条红）

===== test_cancel_during_gate_wait_cancels_future (test_executors.ConcurrencyRobustnessTests.test_cancel_during_gate_wait_cancels_future) =====
  File "…\程序\tests\test_executors.py", line 262, in test_cancel_during_gate_wait_cancels_future
    self.assertTrue(waiting.done())
AssertionError: False is not true

===== test_scale_workers_after_closing_spawns_none (test_executors.ConcurrencyRobustnessTests.test_scale_workers_after_closing_spawns_none) =====
  File "…\程序\tests\test_executors.py", line 288, in test_scale_workers_after_closing_spawns_none
    self.assertEqual(len(pool._workers), before)
AssertionError: 6 != 2

===== test_vendor_limit_removal_wakes_waiters (test_executors.ConcurrencyRobustnessTests.test_vendor_limit_removal_wakes_waiters) =====
  File "…\程序\tests\test_executors.py", line 276, in test_vendor_limit_removal_wakes_waiters
    self.assertEqual(waiter.result(timeout=5), 'ran')
  File "…\concurrent\futures\_base.py", line 456, in result
    raise TimeoutError()
TimeoutError
```

## 修复点（infra/executors.py，全部最小改动）

1. **Future 永久死锁**（原 L176-181）：`_execute_item` 原顺序先 `set_running_or_notify_cancel()`（置 RUNNING）再 `gate.acquire(cancel)`；等闸期间 cancel 令 acquire 返回 False 后，`future.cancel()` 在 RUNNING 态恒 False → `done()` 永 False。修复：先 `gate.acquire(cancel)`（Future 仍 PENDING，cancel 可干净置 CANCELLED），获槽后再 `set_running_or_notify_cancel()`；其返回 False（同时被外部 cancel）时经 `finally` 立刻 `gate.release()` 返回。
2. **拆闸唤醒丢失**（原 L124-126 ＋ acquire 循环）：`set_vendor_limit(v,0)` 仅 pop `_VENDOR_GATES`，不唤醒阻塞在旧 gate 的线程。修复：pop 后对旧 gate 调 `old.set_limit(0)`（内部 notify_all）；同时把 `acquire` 等待循环条件改为 `limit > 0 and in_flight >= limit`——原循环只在入队时查一次 `limit<=0`，等待中被置 0 会让 `in_flight >= 0` 恒真，唤醒后仍困死；新条件使 `limit<=0` 在等待中也直接放行（`limit>0` 行为与原实现逐字等价）。
3. **扩容无锁竞态**（原 L156-166, 220-222）：`_ensure_network_workers` 读 `_POOLS.get('network')` 未持 `_POOLS_LOCK`，`len(pool._workers)` 与建线程未持 `pool._lock` 也未查 `_closing`（shutdown 期间产孤儿线程；两线程并发扩容还会按外部读的旧 len 双重扩容超编）。修复：经 `_pool('network', want)`（内部持 `_POOLS_LOCK`）取池；`add_workers` 改签名接收目标总数 `want`，在 `self._lock` 内查 `_closing`（closing 直接返回）并按 `want - len(self._workers)` 安全扩容。

## 改后绿（本树实测尾部）

```
run_selftests.py -k executors force_quit
…
  test_executors                19 条     3.8 秒
共 40 条用例，6.5 秒；0 个文件有红
ALL TESTS PASSED        （exit 0）

smoke_test.py --architecture
…
Ran 708 tests in 404.053s
OK
✅ 架构治理测试：tests/architecture        （exit 0）
```

## 改动表（git diff --numstat 口径）

| 文件 | 改动 | 内容 |
| --- | --- | --- |
| `infra/executors.py` | +15/−15 | `_execute_item` 先等闸后置 RUNNING；`set_vendor_limit` pop 后 `old.set_limit(0)` 唤醒；`acquire` 循环条件并 `limit>0`；`_ensure_network_workers` 经 `_pool` 取池＋`add_workers(want)`；`add_workers` 持 `self._lock` 查 `_closing` 按目标数扩容。 |
| `tests/test_executors.py` | +64/0 | `ConcurrencyRobustnessTests`：闸门等待期 cancel→done/cancelled 不死锁；`set_vendor_limit(v,0)` 立刻唤醒旧 gate 阻塞者；shutdown 后扩容不产孤儿线程。 |

## 提交状态

- `dev.py claim` → 轮次号 **4493**（基准 377cd201a）。
- 提交命令：`dev.py commit -m "R4493: REF-L1-1 修复 infra/executors.py 三处并发缺陷" infra/executors.py tests/test_executors.py tasks_round/tasks_round_4493_result.md --tests executors force_quit`
- commit hash 以 `git log` 为准。

## 没有验证的地方

- 真实桌面人工看屏未做（并发语义由新增 3 条单测＋既有 16 条 executors 契约覆盖）。
- 高并发压测／长时间 soak 未跑（卡面未要求）。
