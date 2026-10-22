# R1825 结果：压平 run_background 的嵌套（整理轮）

- 改动：`workflow_engines.run_background` 的 Claude JSON 分支抽成 `_run_claude_json`，嵌套深度从 6 降到 5；`NESTING_CAPS` 删除该条（已清空）。
- 差分测试先行：`tests/test_run_background_equivalence.py`，旧实现取 HEAD 原文内嵌（exec），覆盖 Claude 6 种响应/退出码与 codex 2 种退出码，对照 _run 调用、槽位释放、异常与落盘文件；旧实现自比一致。
- 变异检验：把报错文案“响应记录”改成“响应记”，差分测试变红，已还原。
- 验证（本轮运行）：差分测试、`tests.architecture.test_complexity_ratchet`、`run_selftests.py -k workflow_engine` 均通过。
- 断言未动。
