# R2091 合入 claude/fix-copy-rules（R2090：修改习惯文案触发的 test_copy_rules 红项）到 master（合并轮）

轮次类型：合并轮。日期：2026-10-30。

- 合入：分支 `claude/fix-copy-rules` 的 R2090（`32ae91e6`）以 `--no-ff` 合入 master（合并前 master 为 `389007ed` R2086），无冲突。
- R2090 内容：`edit_habits.py` 归纳提示词开头去掉人称（「任务：分析用户对 AI 生成剧本的修改」）；`edit_habits_dialog.py` 弹窗说明两处「你」改为「您」。没有把文件登记进 `PROMPT_FILES` 豁免，因为该文件还有用户可见提示；测试与白名单未改，断言未动。详见 `tasks_round/tasks_round_2090_result.md`。
- 本轮运行（主目录，合并后工作树）：`run_selftests -k test_copy_rules test_edit_habits` 23 条 0 红；默认 `smoke_test.py` 8/8 通过。
- 未运行：`--affected`、架构门禁、`--all --safe`（提交后由后台全量补跑）、真实界面目测。`test_leak_teardown` 时序红未处理。`project_status.md` 债务未减少。未 push。
