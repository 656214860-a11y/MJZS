# R3908 结果
<!-- round-evidence: {"commit_base": "5d010101", "credential_hits": 0, "evidence_sha256": "16a94988eff317a5", "exit": 0, "failed": 0, "passed": 33, "round": 3908, "tests": "run_selftests.py -k lane_flow_gates test_merge_round unification_ratchet"} -->

本轮属于修复轮（§3.2）。测试跑了：默认冒烟 9 项 0 失败；定向 29 条通过（旧车道字符串门禁、合并轮、裸 json.loads 棘轮）。架构门禁全套和安全全量没跑，全量欠账没有减少。

检查点提交把 `release_merge_lane` 写成了直接 `json.loads`，架构棘轮因此多出一条未登记债务，任务书收口分支的出口 CI 在架构门禁失败。本轮改回锁租约的读取，并补上合并道在脏主干、外来变基和临时工作树失败时的退回。

同一次中断里还有游离 HEAD 重叠检查、短心跳截尾、全量让出 GUI 令牌。这些文件和其他活跃车道的未合入改动重叠，提交门拒绝，已留在本分支暂存之外，没有并进这次提交。

验证（vnkl，随附解释器）：

- python -B smoke_test.py：通过 9 项，失败 0（当时工作树还含未提交的重叠文件）。
- python -B -m unittest tests.architecture.test_lane_flow_gates tests.test_merge_round tests.architecture.test_unification_ratchet.UnificationRatchetTests.test_bare_json_load_debt_is_a_nonincreasing_subset：29 条，17.383 秒，OK。
- 架构门禁全套：未运行。
- 安全全量：未运行。

欠账没有少。断言没有放宽。
