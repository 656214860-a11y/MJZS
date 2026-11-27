# R4625 结果：C08 修复复核阻断项（合入 selftest_scheduling、GUI 锁内串行复核、测试归入 test_selftests_gui_token）
<!-- round-evidence: {"commit_base": "06337023b", "credential_hits": 0, "evidence_sha256": "d725339578faaea4", "exit": 0, "failed": 0, "passed": 83, "round": 4625, "tests": "run_selftests.py -k test_selftests test_selftests_gui_token"} -->

- 轮次类型：§3.2 修复轮（自检调度可靠性与架构门禁修复）
- 测试与三基线：`run_selftests.py -k selftests selftest_scheduling` 通过 83 条（2 文件 / 6 单元，0 红、0 跳过，2.1 秒，退出码 0）；`smoke_test.py` 通过 9 项 / 失败 0 项（退出码 0）；`smoke_test.py --architecture` 714/714 全通过（263.6 秒，退出码 0，含 `test_layers`、`test_coverage_baseline`、`test_print_ratchet`、`test_structure`）；三基线通过，无既有断言改动。
- 欠账变化：未新增；清除了 R4618 引入的未登记顶层模块 `selftest_perf_recheck.py` 与错误命名测试文件 `tests/test_selftest_perf_recheck.py`。

## 改动
- 分支 `codex/opt-c08-perf-serial` 已 rebase 到最新 `master`（`704373351`，含 R4620 `codex/gui-wave-regression`）。
- 删除 `selftest_perf_recheck.py` 与 `tests/test_selftest_perf_recheck.py`。
- `selftest_scheduling.py`：合入 `recheck_perf_reds(got, perf_units, runner)`（复用 `_EXCLUDED_STEMS` 调度域，不新增顶层运行期模块）。
- `run_selftests.py`：从 `selftest_scheduling` 导入并对外再导出 `recheck_perf_reds`；在 `run_gui_under_token` 持 `gui_lock` 期间对 `perf_batch` 使用 `run_safe_serial if safe else run_serial` 做非 `--serial` 复核；在 `main` 的 `perf_non_gui` 分支同样用对应 `perf_runner` 仅对 `perf_non_gui` 做非 `--serial` 复核，移除锁外全局复核调用。
- `tests/test_selftests_gui_token.py`（只追加，未改动既有测试）：新增 `PerfRecheckUnitTests`（5 条，8 元组结构）与 `PerfRecheckIntegrationTests`（5 条，覆盖 `acquire`→复核→`release` 锁边界、`--safe` 走 `run_safe_serial`、`perf_non_gui` 无 GUI 锁复核、`--serial` 不重复复核）。
