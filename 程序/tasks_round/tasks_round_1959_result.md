# R1959 修复轮：自动版本检查／续签不再占用独占后台

## 原因
R1958 验证时 `test_ui_edges` 有 2～3 条不稳定红灯：期望的状态文字没出现，状态栏是“检查新版本”。

启动后自动执行的版本检查（`start_update_check`）和定时续签（`start_account_renewal`）都经 `AccountController._run` → `_account_submit` → `async_queued` → `async_`，走的是**独占业务后台**：`worker=True`，`busy_state` 把 label 写进状态栏。联网检查期间用户点任何按钮，`Desktop.safe()` 都会报“当前操作尚未结束，请稍后”。测试只是更容易撞上这段时间，真实用户在启动后几秒内操作也一样会被拦下。

## 改动
- `account_controller.AccountController`：新增可选参数 `background`（不传时等于 `submit`），`_run(..., quiet=)` 按需选通道；`check_update` 恒走 `background`；`renew(quiet=True)` 走 `background`，默认（用户手动续签）仍走 `submit`。
- `desktop_account_page.AccountPageMixin`：新增 `_account_background`，用独立线程执行，经 `win.after` 轮询把结果交回 Tk 主线程；不置 `worker`、不写状态栏，关闭期间不再交付。定时续签改为 `renew(..., quiet=True)`。软提示“有新版本”仍由 `_update_checked` 主动写状态栏一次，这一点不变。
- 新常量 `BACKGROUND_POLL_MS = 100`。

## 测试
- 新增 `tests/test_account_background_checks.py`（5 条）：自动检查与自动续签走 `background`；手动续签仍走 `submit`；不传 `background` 时退回 `submit`；经 `_account_background` 的版本检查不改 `worker`、不写状态栏；关闭后不交付。既有断言未动。

## 验证（经 `gui_hidden.py`）
- `-k account update_notice ui_edges`：216 条全绿（`ui_edges` 115 条全过）。
- `-k ui_edges architecture`：521 条，`ui_edges` 再次全绿；3 个红与本轮无关：`test_agents_md`、`test_skill_reference_injection`（worktree 缺文件，历史红）、`test_round_baselines` 1944 != 1959（状态页只能在 master 同步）。
- `smoke_test.py` 默认集：通过。
- 未跑 `--all --safe`；未在真实窗口目测。
