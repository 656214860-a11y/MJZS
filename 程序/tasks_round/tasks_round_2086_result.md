# R2086 合入 claude/fix-test-isolation（R2081：合并后遗留 3 个红项）到 master（合并轮）

轮次类型：合并轮。日期：2026-10-30。先领 R2084，提交时计数器已被其他会话推进，改领 R2086。

- 合入：分支 `claude/fix-test-isolation` 的 R2081（`29c997b1`）以 `--no-ff` 合入 master（合并前 master 为 `33b684b8` R2080），无冲突；两边改动的文件不相交。
- R2081 内容：`test_writing_api` 正式稿用例隔离本机模型池；`test_core` 假侧栏补 `exists`（R2058 契约变更后同步 mock）；`test_idea_chat` 8 条气泡用例改用 `settle_script_page` 等聊天历史回填。详见 `tasks_round/tasks_round_2081_result.md`。
- 合并时补修：主目录定向自检暴露 `test_idea_chat.BubbleLayoutTests.test_only_what_you_type_below_the_line_gets_sent` 同类时序红（读到「正在读取聊天记录…」），R2081 漏改。已在本合并提交里把该用例 `show(0)` 后的单次 `win.update()` 改为 `self.settle_script_page(win)`。随后全文件扫描「先写历史、`show(0)` 后只刷新一次」的用例，只剩 `test_refresh_is_next_to_interrupt_and_repairs_old_claude_blocks`，它只读文件内容不读日志，未改。
- 只改测试同步，断言未动。
- 本轮运行（主目录，合并后工作树）：`run_selftests -k test_core test_idea_chat test_writing_api` 335 条，补修后连跑 2 次 0 红；默认 `smoke_test.py` 8/8 通过。
- 未运行：`--affected`、架构门禁、`--all --safe`（提交后由后台全量补跑）、真实界面目测。`project_status.md` 债务未减少：这些红项此前未单独登记为待办。未 push。
