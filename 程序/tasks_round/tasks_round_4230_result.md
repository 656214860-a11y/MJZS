# R4230 FIX-ROUNDCLAIM-LOCK：领号锁 PermissionError 并发误杀（修复轮）
<!-- round-evidence: {"commit_base": "729f8800", "credential_hits": 0, "evidence_sha256": "590aee444334e6a6", "exit": 0, "failed": 0, "passed": 28, "round": 4230, "tests": "run_selftests.py -k round_claim dev_entry"} -->

## 三问
- 轮次类型：§3.2 修复轮（主干全量两趟红在 `test_round_claim` 并发领号，卡面 FIX-ROUNDCLAIM-LOCK）。
- 测试跑了吗、三个基线过了吗：定向 `run_selftests.py -k round_claim dev_entry` 改前 3 红、改后 28 条全绿；`smoke_test.py --architecture` 700 条全绿。默认冒烟与全量 `--all --safe` 未跑（卡面只列两条验收命令）。
- 欠账少了吗：无新增欠账；本轮闭环一条并发领号 PermissionError 缺陷。

## L0–L5 盘点
- L0 锁所有权／租约／异常契约：`round-claim.lock` 位于 Git common-dir；`lock_lease.payload()` 写 `pid/token/heartbeat_at/created_at/started_at`，心跳 30 秒、静默 180 秒才可回收；`FileExistsError` 表示锁已存在，`PermissionError(13)` 在 Windows 上是同路径被并发删除／重建时的瞬态占用，不是永久持有。
- L1 Windows 文件边界：`os.open(O_CREAT|O_EXCL)`、`os.stat`、`io.open`、`Path.unlink` 都可能抛 `PermissionError`；建锁、读锁、删锁三处都必须把它当「暂时不可判定／仍被占用」，不能当成缺陷外异常上抛。
- L2 `lock_lease` 状态判定：`inspect()` 返回 `missing/live/stale/unknown`；首次 `os.stat` 原先只容忍 `FileNotFoundError`，`PermissionError` 会穿透；`reclaim()` 只在 `stale` 且文件身份未变时删除，其余一律 False。
- L3 领号编排：`dev.py claim` → `round_claim.py next` → `claim_next()`；`record_claim` 与任务队列操作共用 `shared_lock()`；`_acquire_lock()` 超时 15 秒报 `TimeoutError`，`FileExistsError` 仍先试 `reclaim()`，`PermissionError` 只等待不回收。
- L4 UI／调用方（只读）：无 UI 直接调用；入口为 `scripts/dev.py`、`scripts/merge_round.py` 与自检／提交锁使用方；公开函数签名未变，`lock_lease.inspect()` 对 PermissionError 改为 `unknown` 后调用方按「不可判定／仍占用」处理。
- L5 验证：定向先红后绿、架构门禁、8 线程自动化并发用例验证见下；32 线程手工并发叙述已撤回。

## 缺陷复现方式
在 `tests/test_round_claim.py` 新增 3 条 monkeypatch 回归（145–210 行）：`os.open` 对锁路径前 3 次抛 `PermissionError(13)`、`Path.unlink` 对锁路径前 2 次抛 `PermissionError(13)`、`os.stat` 对锁路径抛 `PermissionError(13)`；分别断言 `claim_next` 仍返回正确号、`shared_lock` 退出不抛且锁被删、`lock_lease.inspect/reclaim` 按占用处理不抛。

## 改前红（未改产品，退出码 1）
命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k round_claim dev_entry`（工作目录 `程序`，PowerShell）

输出尾部原文：
```
共 28 条用例，19.4 秒；1 个文件有红
### test_round_claim（3 条红）
===== test_claim_retries_permission_error_while_lock_is_being_replaced =====
PermissionError: [Errno 13] 另一个程序正在使用此文件，进程无法访问。
===== test_lock_lease_permission_error_is_treated_as_occupied =====
PermissionError: [Errno 13] 另一个程序正在使用此文件，进程无法访问。
===== test_shared_lock_retries_permission_error_when_removing_lock =====
PermissionError: [Errno 13] 另一个程序正在使用此文件，进程无法访问。
```
红因与缺陷一致：`_acquire_lock` 只捕 `FileExistsError`，`lock_lease.inspect` 首次 `os.stat` 只容忍文件不存在，`shared_lock` 删除只容忍 `FileNotFoundError`。

## 改动（最小面）
- `维护记录/基准脚本/round_claim.py:234-240`：`_acquire_lock` 捕获 `(FileExistsError, PermissionError)`；仅 `FileExistsError` 先试 `lock_lease.reclaim()`，两者都在 deadline 后抛 `TimeoutError`，等待间隔仍 0.05 秒。
- `维护记录/基准脚本/round_claim.py:256-266`：`shared_lock` finally 里 `lock_lease.release()` 后删除锁；`PermissionError` 最多重试约 2 秒（间隔 0.05 秒），仍失败则保留锁文件不抛，`FileNotFoundError` 照旧忽略。
- `维护记录/基准脚本/lock_lease.py:87-88`：`inspect()` 首次 `os.stat` 遇 `PermissionError` 返回 `("unknown", {}, None)`，使 `reclaim()` 得 False（按仍占用），不向上抛。
- `tests/test_round_claim.py:145-210`：新增上述 3 条测试；既有断言（含 8 线程并发与 `range(41, 49)`）未改。

## 改后验证（命令正文逐字，工作目录 `程序`，PowerShell）
1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k round_claim dev_entry` → 退出码 0，输出尾部：
```
共 28 条用例，23.0 秒；0 个文件有红
ALL TESTS PASSED
```
2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 退出码 0，输出尾部：
```
Ran 700 tests in 281.564s
OK
✅ 架构治理测试：tests/architecture
```
3. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` → 退出码 0，轮次号 4230。

返工说明（R4234）：本节原先记录的 32 线程首跑与五连跑叙述没有保留可核验原始输出，验收 N321 判定为无凭据手工并发叙述；该叙述已撤回，不作为 R4230 验收证据。document-only 真实性补正见 `tasks_round/tasks_round_4234_result.md`。

## 手工并发验证（32 线程 × 5，原始输出缺失，叙述已撤回）
- 可核实的自动化并发用例仍是 `tests/test_round_claim.py` 的 `test_concurrent_claims_are_unique_and_contiguous`：8 线程、期望号段 `range(41, 49)`，未弱化；本轮定向证据见 round-evidence 机器头与上方 28 条全绿记录。
- 原先记录的“32 线程首跑 errors 为空、号段 41–72”“期望仍写 8 个号”“同一定向命令五连跑全绿”等手工并发叙述，因未找到原始输出而撤回；不得作为本轮验证证据。
- R4234 document-only 补正未为本文档修改测试、重跑 32 线程试验或补造输出；测试保持 8 线程与 `range(41, 49)`。

## 提交
- `git diff --numstat` 原文由验收角色复跑；提交前工作树仅含本卡允许文件。
- 本结果文件与 `tasks_round/evidence/R4230.json` 由 `scripts\dev.py commit` 同批生成／提交；提交哈希无法在同批文件内自引用，以证据回执与完成报告为准。
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4230: FIX-ROUNDCLAIM-LOCK 修复" 维护记录/基准脚本/round_claim.py 维护记录/基准脚本/lock_lease.py tests/test_round_claim.py tasks_round/tasks_round_4230_result.md --tests round_claim dev_entry`

## 没有验证的地方
- 未复现真实多进程／安全软件短暂占用，只用 monkeypatch `PermissionError(13)` 与 8 线程自动化并发用例验证；未跑默认冒烟、全量 `--all --safe`。
- `merge_round.acquire_merge_lane()` 自身 `os.open` 仍只捕 `FileExistsError`（见下），不在本卡允许文件内，未改。

## 卡外发现（只记录）
- `scripts/merge_round.py:273-275` 与 `selftest_scheduling.py:38-39` 的 `os.open`/`os.link` 也只按 `FileExistsError` 重试，理论上可能遇到同类 Windows `PermissionError`；本卡范围外，未动。
