# R986 结果：全量凭据脏树前置守卫

- 本轮是功能/可靠性轮：为 `reliability-loss-guard` 落地首项防损约束，队列项仍保持认领，未误报整项完成。
- 测试已跑：定向 `tests.test_selftests_gui_token tests.test_selftests` 48/0；默认冒烟 8/8；架构门禁 279/0（99.026 秒）；完整安全全量 3821/0（297.0 秒）。
- `project_status.md` 的主干欠账以 common-dir receipts 为准；本轮刷新了 R986 内容树凭据，待本结果提交后的最终复验再确认最终树。

## 交付

- `run_selftests.py --all --safe` 在取得全量锁后、启动任何子进程前，复用 `content_tree()` 的工作树状态判据；脏树逐项打印根路径和状态，并以“脏树不会产凭据”拒绝。
- 新增 `--allow-dirty-diagnostic`：打印 `[NO_RECEIPT]`，允许只诊断运行，但不写全量凭据、分层基线或增量台账。
- 补齐 GUI 锁回归的前置守卫 mock；两把锁的取得顺序、异常抛出与释放断言不变。

## 现场凭据

- 脏树现场命令 `python run_selftests.py --all --safe --force` 输出两个脏文件并返回 2，未启动子进程。
- 提交：`983edea R986: guard full-safe receipts against dirty trees`（本结果提交后会 amend 为最终哈希）。
- 未改动 `test_asset_gating` 或 `test_pet_settings`，未触碰用户项目、`程序/data`、`程序/private`、日志或运行数据。
