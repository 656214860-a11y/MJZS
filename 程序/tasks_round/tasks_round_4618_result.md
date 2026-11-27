# R4618 结果：C08 性能用例并发红时串行复核
<!-- round-evidence: {"commit_base": "6507c0dbe", "credential_hits": 0, "evidence_sha256": "dcf3f4d955b27b89", "exit": 0, "failed": 0, "passed": 75, "round": 4618, "tests": "run_selftests.py -k test_selftest_perf_recheck test_selftests"} -->

- 轮次类型：§3.2 修复轮（测试调度可靠性）
- 测试：新增单测 3 个 OK；`smoke_test.py --affected selftest_scheduling run_selftests` 通过 10 项，门禁 9 模块 ALL TESTS PASSED；三个基线通过
- 欠账：未新增

## 改动
- `selftest_perf_recheck.py`（新模块，为避开 codex/gui-wave-regression 对 selftest_scheduling.py 的未合入改动）：新增 `recheck_perf_reds(got, perf_units, runner)`。性能单元在全量里变红时，串行单跑复核一次，复核后仍红才判红；断言不变，非性能单元的结果原样保留。
- `run_selftests.py`：汇总结果后调用 `recheck_perf_reds(got, perf, run_serial)`。
- `tests/test_selftest_perf_recheck.py`：覆盖三种情况，即复核转绿、复核仍红、非性能红不复核。

## 提交
分支 codex/opt-c08-perf-serial，commit hash 以提交输出为准。
