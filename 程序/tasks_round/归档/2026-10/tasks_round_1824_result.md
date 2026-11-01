# R1824 结果：压平 run_batch 的嵌套（整理轮）

- 改动：`asset_batch_execution.run_batch` 的失败分支抽成 `_record_failure`，嵌套深度从 6 降到 5；`NESTING_CAPS` 删除该条。
- 差分测试先行：`tests/test_asset_batch_failure_equivalence.py`，旧实现取 HEAD 原文内嵌，覆盖 8 种异常 × 5 种台账初态，对照台账内容与 save_ledger 调用。
- 变异检验：把 `'failed'` 改成 `'faile'`，差分测试 4 项变红，已还原。
- 验证（本轮运行）：差分测试、`tests.architecture.test_complexity_ratchet`、`run_selftests.py -k asset_batch` 均通过。
- 断言未动。
