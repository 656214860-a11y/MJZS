# R1728：修复轮——GUI 测试令牌排队与按需占用＋缩略图后台进程收尾（LOCKQ）

## 三个问题

1. **本轮类型**：修复轮（GUI 令牌生命周期/排队 + 缩略图 worker 收尾），含测试补强。未改 `project_status.md`，未领号、未提交。
2. **测试跑了吗、三个基线过了吗**：
   - 默认冒烟：8/8 通过。
   - 架构门禁：`smoke_test.py --architecture` 368 条，0 失败，退出码 0。
   - 全量回归：**未运行**（任务书明确“不跑全量”），未写入或冒用全量绿凭据。
   - 定向：`run_selftests.py -k selftests asset_thumbs` 88 条 / 0 红；`--serial` 同范围 88 条 / 0 红。
   - 消费者冒烟：`smoke_test.py --affected run_selftests asset_thumbs` 9/9 通过，门禁 0 红。
3. **`project_status.md` 的欠账少了吗**：未改状态页（执行方不写）。本轮闭环了 `test_asset_thumbs` 的红项事实，但状态页欠账需由提交方按流程更新。

## 改前红（先写测试、先跑红）

新增/加强的 GUI 令牌测试在旧实现上（当时该文件 11 条；后又补 2 条时序/性能单元用例，最终 13 条）：

```text
FAIL: test_cli_gui_timeout_lists_names_no_pass_no_cache_for_default_and_k (args=[])
  AssertionError: 'GUI 测试 1 个未运行' not found ...
FAIL: test_gui_module_skipped_by_incremental_never_takes_the_token
  AssertionError: Expected 'acquire_gui_lock' to not have been called. Called 1 times.
ERROR: test_non_gui_units_finish_before_token_and_release_follows_gui
  ValueError: list.index(x): x not in list
ERROR: test_waiters_are_served_in_arrival_order
  AttributeError: module 'run_selftests' has no attribute 'GUI_QUEUE_NAME'
ERROR: test_waiting_reports_holder_pid_start_and_elapsed
  AttributeError: module 'run_selftests' has no attribute 'GUI_WAIT_NOTICE_SECONDS'
Ran 11 tests ... FAILED (failures=4, errors=3)
```

新增的 `reset_worker` 测试在旧实现上：

```text
FAIL: test_reset_worker_kills_and_reaps_a_worker_that_ignores_terminate
  AssertionError: None is not true : 收掉进程后必须返回成功
FAIL: test_reset_worker_reports_when_the_process_cannot_be_reaped
  AssertionError: '未能在' not found in ''
Ran 2 tests ... FAILED (failures=2)
```

旧实现还会把 `TimeoutExpired` 记成 “已忽略” 后继续返回，调用方拿不到“未收掉”的结果。

## 改动

### `run_selftests.py`

- 不再在 `import_all()` 前按“选中的文件里有 GUI 模块”提前占牌。改为：
  - 先发现工作单元，并区分非 GUI / GUI；
  - **非 GUI 单元先跑**（不持有 GUI 令牌）；
  - 只有确实要执行 GUI 单元（含 GUI 性能单元）时才申请令牌；
  - GUI 单元跑完立刻在 `finally` 中释放，不等汇总、台账或进程退出。
- GUI 令牌增加跨进程排队：
  - `gui-selftest.queue/` 下按纳秒到达时间取票，只有队首能尝试拿锁，后到者不再每 0.1 秒插队；
  - 等待期间立即打印一行、之后每约 30 秒打印 `[GUI_WAIT]`：占用者 PID、开始占用时间、已占用时长、本进程已等时长、队列位次；
  - 超时退出排队并打印 `[GUI_DEFERRED]`。
- 超时汇总新增明确计数：`GUI 测试 N 个未运行（等待令牌超时，未执行、未计入通过）：...`；有未运行 GUI 测试时不打印 `ALL TESTS PASSED`，不写增量台账/分层基线，退出码为 2（若同时有红则为 1）。
- `--serial` 的非 GUI 单元仍走 `run_serial`，不会被改成并行池。
- 未改 `-k`、`--serial`、`--all --safe`、增量台账、`--gui-wait` 的参数语义。

### `asset_thumbs.py`

- `reset_worker(timeout=2.0)`：
  - `terminate()` 后 `wait` 超时 → 升级 `kill()` 再 `wait`；
  - 收不掉时返回 `False` 并写 `asset_thumbs` 的 warning 日志，不再静默吞掉 `TimeoutExpired`；
  - 收掉（或本来没有 worker）返回 `True`；仍会清空 `_WORKER`，避免旧缓存目录的句柄被误用。
- 新增 `logging` 引入；无新增 `print`。

### 测试

- `tests/test_selftests_gui_token.py`：新增“被增量跳过的 GUI 文件不占牌”“非 GUI 先跑、GUI 期间持有、GUI 后立即释放”“GUI 性能单元在牌内、其余性能单元在释放后”“超时汇总计数”“等待状态行”“多进程先到先得”“`--serial` 仍走串行 runner”用例；调整原超时/释放用例的 mock 时序与断言。
- `tests/test_asset_thumbs.py`：新增 `WorkerResetTests`，覆盖 terminate 超时后 kill 收掉、以及 kill 也收不掉时返回 `False` 并记录 warning。
- 未删除或弱化原有断言；令牌超时用例从“只断言 `[GUI_DEFERRED]`”加强为同时断言“GUI 测试 1 个未运行”、无 `ALL TESTS PASSED`、不写缓存/凭据。

## 实际计数

| 命令 | 结果 |
| --- | --- |
| `python -B run_selftests.py -k selftests asset_thumbs` | 3 个文件 / 7 路单元，**88 条，0 红**，6.9 秒，退出 0 |
| `python -B run_selftests.py --serial -k selftests asset_thumbs` | 3 个文件 / 7 路单元，**88 条，0 红**，11.2 秒，退出 0 |
| `python -B run_selftests.py -k test_asset_thumbs --force` 第 1 次 | **23 条，0 红**，6.1 秒，退出 0 |
| 第 2 次 | **23 条，0 红**，5.5 秒，退出 0 |
| 第 3 次 | **23 条，0 红**，5.3 秒，退出 0 |
| `python -B smoke_test.py --affected run_selftests asset_thumbs` | 9/9 通过，门禁 0 红，退出 0 |
| `python -B smoke_test.py --architecture` | **368 条，0 失败**，283.482 秒，退出 0 |
| `python -B smoke_test.py` | 8/8 通过，退出 0 |
| `python -B run_selftests.py -k module_size function_size print_ratchet` | 6 条，0 红（改后复核尺寸/print 棘轮），退出 0 |

三次 `test_asset_thumbs --force` 为连续执行，未中途停掉重跑。

## 需裁决 / 说明

1. **超时计数单位**：`GUI 测试 N 个未运行` 的 N 是“计划执行但被令牌超时挡下的测试文件数”，与 `[GUI_DEFERRED]` 后面的模块名一致，不是用例条数。若要求按用例条数统计，需要把 deferred 单位改为用例数。
2. **测试契约变化**：`test_cli_gui_timeout...` 的 `units` mock 改为返回真实 GUI 工作单元，因为占牌时点已后移到“发现要跑哪些单元”之后；原“选中的文件里有 GUI 就提前占牌”的旧契约不再成立，但超时不得计通过、不得写台账/凭据的断言保留并加强。`test_full_lock_then_gui...` 的异常注入点从 `protect_tk` 移到 `run_units`，因为 GUI 锁现在确实在更晚的时点才申请；仍然断言异常时全量锁与 GUI 锁都释放。
3. **`reset_worker` 的通知方式**：通过返回 `False` + warning 日志让调用方知道；测试收尾若收不掉，会让临时目录清理撞上占用错误，因此 `test_asset_thumbs` 能发现。`run_selftests.cleanup_unit_helpers()` 仍按原样用 `try/except` 包住，不检查返回值；若要求 runner 汇总层也单独展示这条 warning，需要再加一条登记输出（本轮未做）。
4. **共享基线文件**：本轮验证过程中曾出现 `维护记录/测试分层基线.json` 被工具刷成精简形态（不是本轮允许改动的文件），已按 HEAD 字节恢复；最终 `git status` 不含该文件。最终工作树只有下面四个代码/测试文件（外加本结果文件）有改动。
5. **未运行**：未跑 `run_selftests.py --all --safe`（全量），未跑真实 GUI 应用启动；`auto-full-safe-result.json` 的历史红项以任务书描述为证据，未另开真实用户项目。

## 工作树

仅以下文件改动（`git status --short` 已核对）：

- `程序/run_selftests.py`
- `程序/asset_thumbs.py`
- `程序/tests/test_selftests_gui_token.py`
- `程序/tests/test_asset_thumbs.py`
- `程序/tasks_round/tasks_round_pending_LOCKQ_result.md`（本文件）

没有执行 git 写命令，没有提交，没有领号，没有改 `project_status.md`。

## 独立验收（Claude，主工作区）

- 车道 diff 在 R1727 之上干净应用。
- `run_selftests.py -k selftests asset_thumbs`：0 红，ALL TESTS PASSED。
- `smoke_test.py` 默认 8/8；`--architecture` 368 条 1 红：仅全量欠账（8 个源码轮后由提交钩子后台自动补跑，不阻断）。
- 未运行：全量安全回归（交给后台自动补跑）。
