# R1863 结果：修自检器 GUI 令牌队列路径斜杠不一致，队首永不命中（修复轮）

- 三问：本轮是 §3 修复轮：改 `run_selftests.py` 两行、加 1 条测试；验证见下；`project_status.md` 欠账未变（分支不写状态页）。
- 计划来源：vibe coding 体检计划批次 4 全量中发现；队列无对应 ID。接 R1861（test_force_quit 修复）。

## 修复：GUI 令牌队列永远认不出队首（自检器既存缺陷）
`git_common_dir()` 原样返回 git 给的 `D:/repo-meta/…`（正斜杠），`_join_gui_queue` 用 `tempfile.mkstemp`，它返回 `abspath` 规范化后的 `D:epo-meta\…`；`_gui_queue_is_first` 拿 `os.path.join(queue, name)` 与之做字符串比较，永不相等。于是首次抢锁失败的进程（别的树正占令牌）进队后**永远排不到队首**，锁释放了也不去拿，等满 900 秒后 `GUI_DEFERRED`，112 个 GUI 测试文件未执行。本轮第二次全量即如此（日志里“占用者 PID ?／队列第 2 位”而队列只有自己一张票）。
- 改法：`git_common_dir()` 与 `_gui_queue_dir()` 都过 `os.path.abspath`。
- 新测：`test_selftests_gui_token.test_wait_succeeds_with_forward_slash_common_dir`，改前红（`GUI_DEFERRED`）、改后绿。
- 验证：`test_selftests_gui_token`、`test_selftests`、`test_pid_reuse_tokens`、`test_round_claim`（隐藏桌面）84 条全过。

## 验证
（全量待补）
