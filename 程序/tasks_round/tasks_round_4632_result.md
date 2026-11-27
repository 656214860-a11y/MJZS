# tasks_round_4632_result — C21 三虎停滞提醒支持多阶段合并提示
<!-- round-evidence: {"commit_base": "8991b93f4", "credential_hits": 0, "evidence_sha256": "964e04bad571e42a", "exit": 0, "failed": 0, "passed": 677, "round": 4632, "tests": "run_selftests.py -k pet_ui pet_state"} -->

- **本轮类型**：§3.1 功能轮（三虎阶段停滞提醒在多个阶段同时卡住时，由「只报首个且吞掉其余」改为「一次检出全部满时限阶段并合并成一条提示」，单阶段文案与 `StallWatch.sample()` 签名完全向后兼容）。
- **测试与三基线**：
  - 改前先红：`run_selftests.py -k pet_ui_voice` 退出码 1（共 123 条用例，新增 4 条全红，其余 119 条通过）。
  - 改后全绿：
    - `run_selftests.py -k pet_ui pet_state` 退出码 0（共 677 条用例 / 7 个测试文件 / 53 路工作单元，0 失败，0 跳过，31.9 秒，`ALL TESTS PASSED`）。
    - `smoke_test.py` 退出码 0（通过 9 项，失败 0 项）。
    - 架构与规范门禁（`test_coverage_baseline`、`test_module_size_ratchet`、`test_complexity_ratchet`、`test_function_size_ratchet`、`test_static_hygiene`、`test_constant_condition_ratchet`、`test_silent_exception_ratchet`、`test_layers`、`test_structure`、`test_copy_rules`、`test_pet_context_facts`）：105 条用例全过，退出码 0。
  - 三基线说明：本轮未增删生产模块，覆盖率基线模块集合与 `runbook.md` §11 计数不变；性能与分层基线未退化（`ui/pet_context_facts.py` 129 行 ≤ 1000 行上限，函数行数与嵌套深度均远低于阈值）。
- **欠账变化**：清除了 R4353 遗留的「多阶段同时卡住只报首个且将其余阶段误标记为已报导致漏报」欠账，未新增欠账。

## 改动摘要

1. `ui/pet_context_facts.py`：
   - `StallWatch.sample_all(stages, at=None)`：一次遍历收集全部满足停滞条件且本波未报的 `(stage, minutes, done, total)` 列表并各自闩锁，不再丢失并列停滞阶段。
   - `StallWatch.sample(stages, at=None)`：保留既有单命中返回 `(stage, minutes, done, total) | None` 兼容接口，委托 `sample_all`。
   - `format_stall_notes(hits)`：0 条返回空串；1 条直接委托 `format_stall_note(*hits[0])` 保持单阶段文案逐字不变；2 条及以上合并为单行提示 `【阶段停滞】有 N 个阶段没有新进度：「阶段A」已跑 M1 分钟（完成 d1/t1）；「阶段B」已跑 M2 分钟（完成 d2/t2），要我看看吗？`。
   - `stall_note(voice, at=None)`：改为调用 `watch.sample_all` + `format_stall_notes`。
2. `tests/test_pet_ui_voice.py`（仅追加 4 条新用例，未改动/弱化任何既有断言）：
   - `StallWatchTests.test_stall_watch_sample_all_collects_multiple_stalled_stages`
   - `StallWatchTests.test_stall_watch_format_stall_notes_merges_multiple_stages`
   - `StallVoiceTests.test_stall_watch_merges_multiple_stalled_stages_into_one_note`
   - `StallVoiceTests.test_stall_watch_snooze_merges_multiple_stalled_stages_after_expiry`
