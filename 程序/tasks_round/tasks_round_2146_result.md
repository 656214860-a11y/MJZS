# R2146 结果：合入 codex/wip-R2144（R2144：最小化留在任务栏，不再收进托盘）到 master（合并轮）

## 合并
- 来源：`codex/wip-R2144` 的 R2144（ad52913e），基于 d100e72a；master 当时为 f7a8dcc8（含 R2143／R2145）。合并前主检出暂存区有 R2143 会话的改动，等它提交为 R2145、暂存区清空后才合并。`git merge --no-ff`，无冲突。
- 合入内容：`desktop_tray.py` 去掉最小化收进托盘（`<Unmap>` 绑定、`_on_minimize_to_tray`、`_tray_minimized`），托盘图标与右键菜单保留；`tests/test_desktop_tray.py` 最小化循环测试的期望状态改为 `iconic,normal,…`（契约有意变更，不是弱化断言）。

## 验证（本轮运行，主检出合并后）
- `run_selftests -k desktop_tray pet_ui desktop_shell`（经 gui_hidden）：ALL TESTS PASSED；托盘 2 条因隐藏桌面没有任务栏宿主而跳过（R2144 已在交互桌面跑过，7 条通过）。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：411 条中 410 条通过；1 条失败是 `test_round_baselines.test_full_safe_all_is_required_after_eight_source_rounds`（上次全量 R2124 以来已有 8 个改源码的轮次，欠一次完整安全全量），与本次改动无关，按提示不手动全量，由本次提交的 post-commit 钩子后台补跑。
- 未跑全量；未在真实应用里手动最小化看白点。
