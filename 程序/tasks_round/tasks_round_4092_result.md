# R4092 结果：后台全量加暂缓开关
<!-- round-evidence: {"commit_base": "7ea1ddeb", "credential_hits": 0, "evidence_sha256": "802bab01a46f3b45", "exit": 0, "failed": 0, "passed": 58, "round": 4092, "tests": "run_selftests.py -k auto_full_safe full_safe_merge_gate"} -->

## 开头三问

（一）本轮属于哪种类型：功能轮——改的是开发流程工具 `scripts/auto_full_safe.py` 和合并门禁的一处判断，不是产品功能。任务卡 V-FULL-HOLD、车道 codex/full-hold-switch，来源是用户 2026-11-22 20:31 批准的「后台全量加暂缓开关」。

（二）测试跑了吗、三个基线：定向测试 `run_selftests.py -k auto_full_safe full_safe_merge_gate` 实测 58 条用例全过（0 个文件有红，ALL TESTS PASSED）；架构门禁 `smoke_test.py --architecture` 实测 696 条、298.6 秒、失败集合为空；默认冒烟没单独跑；全量自测没跑。新增 11 条用例（HoldTests 10 条＋合并门禁 1 条），没有修改或删除现有用例的断言。

（三）欠账少了吗：全量欠账本轮不增不减。本轮改的是欠账的补跑时机和合并门禁的一处判断：暂缓生效期间 `decide()` 一律返回 wait（不起全量），等待者照旧轮询、到点自动补跑；欠账照记，`status()` 新增 `hold` 字段，`--status` 输出显示暂缓到几点；暂缓期间合并门禁的欠账项不报红。

## 改了哪些文件

- `scripts/auto_full_safe.py`：新增 HOLD_NAME/HOLD_MAX_SECONDS 常量与 `_hold_path`/`hold_until`/`set_hold`/`clear_hold`/`_hold_label` 五个函数；`status()` 加 `hold` 键；`decide()` 在 stop 判断后加暂缓即 wait；`wait_run()` 因暂缓等待时刷新等待者锁 mtime；`_run_locked()` 首句 `clear_hold()`；`_dispatch()` 加 `--hold`/`--release` 两个开关，状态行追加「暂缓」；文件头用法说明补两条。
- `tests/test_auto_full_safe.py`：新增模块级 `setUpModule`/`tearDownModule` 把 `_hold_path` 指到临时目录；新增 `HoldTests` 10 条用例，其 `setUp` 另有逐用例补丁兜底（按类拆分的工作单元不经模块 fixture）。
- `tests/architecture/test_round_baselines.py`：欠账项在 `auto_full_running()` 判断后加两行——`hold_until()` 为真即放行，欠账照记。
- `tests/test_full_safe_merge_gate.py`：`drive()` 加仅关键字参数 `hold=0.0` 并打桩 `hold_until`；新增「暂缓生效时放行」用例（cooling='time' 和 '' 各断言一次不抛）；文件头补一句。原 7 条用例未动。
- `runbook.md`：在「后台自动补跑」段后新增「暂缓」一段，写清用途、两条命令、等待者行为、欠账与门禁口径、12 小时封顶与两道防无限期限制、只在用户明确要求时设置。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git -c core.quotepath=false status --porcelain` | 0 | 无输出（工作树干净） |
| `git log -1 --format=%h` | 0 | `7ea1ddeb` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/full-hold-switch` |
| `git -c core.quotepath=false diff --stat` | 0 | 恰好 5 个文件，+306/-5 |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k auto_full_safe full_safe_merge_gate`（bash 首发） | 127 | bash 不认反斜杠相对路径，未执行；改以 PowerShell 原样重发 |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k auto_full_safe full_safe_merge_gate` | 0 | 共 58 条用例，0.9 秒；0 个文件有红；ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | Ran 696 tests in 298.623s，OK |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 输出 4092 |

## 如实说明

- 暂缓期间合并门禁的欠账项不报红，这是规则上的放宽，由用户 2026-11-22 批准；欠账仍照记，`--status` 与 `status()` 的 `hold` 字段可见。
- 12 小时封顶（从第一次设置算起，续设不顺延）和「一轮全量真的开始即清除（含手动 `--run`、夜间任务）」是防止无限期暂缓的两道限制；距第一次设置满 24 小时后才可重新设置。
- 等待者进程在暂缓期间一直存活并每 60 秒轮询一次；因暂缓等待时刷新等待者锁 mtime，否则 `_waiter_running()` 会把超过 `MAX_WAIT_SECONDS + 600` 秒的锁当成崩溃遗留。
- 机器重启或等待者被杀后，要靠下一次提交、`--release`、`--hold` 或夜间任务重新起等待者。
- 接口契约全部照做；无未照做条目。补充一点：按 `units()` 的按类拆分机制（>20 条即拆），工作单元不经 `setUpModule`，故 `HoldTests.setUp` 里又加了逐用例的 `_hold_path` 补丁兜底，保证任何运行模式下用例都碰不到 git 公共目录里的真实暂缓文件。

## 未覆盖项

- 没有在真实的 post-commit 钩子里走一遍 `--spawn` → 等待者 → 到点补跑的完整链路（卡面禁止运行 `auto_full_safe.py` 本身，它动全仓共用状态）。
- 没有跑全量自测；默认冒烟未单独跑（架构门禁已含相关检查）。
- 未验证 `--hold` 生效后真实等待者跨小时的锁刷新（用例以 mock clock 覆盖了超过 `MAX_WAIT_SECONDS` 的路径）。
- 未验证暂缓文件被人工写入其他非法内容时的全部形态（覆盖了乱码、非对象、非数字、bool、超 12 小时上限五类）。
