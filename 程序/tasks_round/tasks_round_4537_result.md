# tasks_round_4537_result — INFRA-LOCK-SCAN-FIX 减红 R2-G4 + 全量锁卡死治理 P1-1/P1-2 + 分层收口 W6
<!-- round-evidence: {"commit_base": "faa0434ce", "credential_hits": 0, "evidence_sha256": "d2961844afa4f4f7", "exit": 0, "failed": 0, "passed": 62, "round": 4537, "tests": "run_selftests.py -k selftests_gui_token merge_round lane_merge_queue"} -->

- 本轮属于 §3.2 修复轮（卡面 INFRA-LOCK-SCAN-FIX：一次性收口三项既有基础设施阻塞，基准 `faa0434ce`，车道 `codex/infra-lock-scan-fix`）。
- 测试跑了吗、三个基线过了吗：跑了。严格先红后绿——4 条先红测试实跑确认红灯（原文见下），修复后卡面 2 条验收命令实跑全绿、退出码均 0：`run_selftests.py -k selftests_gui_token merge_round lane_merge_queue`（62 条 0 红）；`smoke_test.py --architecture`（708 条 OK）。默认冒烟未单跑（卡面未要求，如实记「未运行」）。全量回归 `--all --safe` 未跑（分支车道不累计）。
- 欠账少了吗：全量锁卡死治理任务书 P1-1/P1-2 落地，`GUI_WAIT_SECONDS` 1800→300 与持锁者心跳年龄输出到位；减红第二步 R2-G4 收口；分层收口 W6 完成。零新增生产模块、零新增测试文件（先红测试落在既有 `tests/test_selftests_gui_token.py` 与 `tests/test_merge_round.py`，不触 `governance/structure.json` 的 test_ownership 门禁）；无新增欠账。

## 先红原文（修复前实跑，退出码 1）

```
===== test_gui_wait_seconds_is_capped_at_five_minutes =====
AssertionError: 1800 != 300

===== test_production_scan_excludes_logs_and_runtime_dirs =====
AssertionError: 'logs' not found in frozenset({'.git', 'voice_asr_venv', '维护记录', '.wt', 'tasks_round', '__pycache__', 'tests', '.selftmp'})

===== test_wait_report_shows_holder_heartbeat_age =====
AssertionError: Regex didn't match: '心跳距今 \\d+ 秒' not found in '[GUI_WAIT] 等待跨树 GUI 令牌：占用者 PID 123456，自 2026-11-26 15:11:40 起（已占 45 秒），本进程已等 30 秒（队列第 1 位）\n'

===== test_clean_lane_already_containing_master_skips_rebase =====
AssertionError: <MagicMock name='_rebase_in()' id='2495470831328'> != 0
```

## 修改摘要（仅卡面允许文件）

- `tests/architecture/_scan.py`：`EXCLUDED_PARTS` 补 `'logs'`、`'data'`、`'outputs'`（R2-G4）。三者均为 .gitignore 忽略的运行目录（`.gitignore:10/19/102`）；全树核实 `程序/**/{logs,data,outputs}/**/*.py` 为零个文件，扫描集不变、已有架构门禁计数与基线不受影响。
- `selftest_env.py:105`：`GUI_WAIT_SECONDS` 1800→300（P1-1）。有意契约变更：全仓 grep 核实无任何测试硬编码 1800 断言该常量（`test_auto_full_safe.py:474` 的 1800 属 `set_hold` 30 分钟逻辑，与本常量无关），无需同步旧断言。
- `selftest_scheduling.py`：新增 `_gui_heartbeat_text(holder)`（读 `heartbeat_at`，兼容旧键 `heartbeat`，缺失/不可读报「心跳未知」）；`_gui_wait_report` 输出行补「心跳距今 N 秒」；`_gui_deferred` 超时报告追加 `（持锁者…）` 心跳尾注（P1-2）。
- `scripts/merge_round.py`：`rebase_onto_master` 在 `ancestor=True` 且分支检出在工作树时，先做与 `_rebase_in` 同口径的脏树检查（脏仍 `REBASE_RETURNED`），干净直接 `return 0`，不再无谓变基（W6：保合并提交、免重放）。
- `tests/test_selftests_gui_token.py` +34 / `tests/test_merge_round.py` +9：4 条先红测试（上个中断会话遗留，本轮在其上完成卡面，未 reset/checkout/丢弃）。

## 验收命令实测

- `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k selftests_gui_token merge_round lane_merge_queue` → 退出码 0，尾部：`共 62 条用例，11.2 秒；0 个文件有红 … ALL TESTS PASSED`
- `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 退出码 0，尾部：`Ran 708 tests in 532.157s / OK / ✅ 架构治理测试：tests/architecture`

## git diff --numstat 原文

```
9	1	程序/scripts/merge_round.py
1	1	程序/selftest_env.py
24	8	程序/selftest_scheduling.py
3	1	程序/tests/architecture/_scan.py
9	0	程序/tests/test_merge_round.py
34	0	程序/tests/test_selftests_gui_token.py
```

## 提交状态

- `dev.py claim` → 轮次号 **4537**。
- 提交命令：`dev.py commit -m "R4537: INFRA-LOCK-SCAN-FIX 减红 R2-G4 + 全量锁卡死治理 P1-1/P1-2 + 分层收口 W6" tests/architecture/_scan.py selftest_env.py selftest_scheduling.py scripts/merge_round.py tests/test_selftests_gui_token.py tests/test_merge_round.py tasks_round/tasks_round_4537_result.md --tests selftests_gui_token merge_round lane_merge_queue`
- commit hash 以 `git log` 为准。不合入、不 push。

## 没有验证的地方 / 观察项

- 默认冒烟 `smoke_test.py`（无参）未单跑：卡面只要求 `--architecture`，本条如实记「未运行」。
- `--architecture` 输出含「棘轮提示」LR-09/LR-10 实测 59 < 基线 60（提示下调 `层间合规清单.json`，非失败）：本树 `logs`/`data`/`outputs` 下本无任何 .py，`EXCLUDED_PARTS` 变更前后扫描集逐文件一致，该差值为车道树与基线源的既有漂移，留主干判读、不在本卡处置范围。
- 心跳年龄仅观察性输出，不改变锁租约、回收与排队判定语义。
