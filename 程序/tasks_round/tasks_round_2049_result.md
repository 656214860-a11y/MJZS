# R2049 合入 codex/wip-R2048 到 master（合并轮）

轮次类型：合并轮。日期：2026-10-25。

- 合入分支 `codex/wip-R2048`（R2048，`30a355fa`：未登录或授权失效时锁定付费页面）。master 已前进到 R2047，非快进合并，自动合并无冲突。
- 与 R2046 同改了 `desktop_login_gate._login_gate_passed`、`desktop_account_page`、`tests/test_login_gate.py`。核对合并结果：R2046 的“登录后重画账号页”与 R2048 的刷新侧栏锁标记都在。
- 合并后验证（在 R2047 之上实跑）：
  - `run_selftests -k page_lock account login membership entitlement desktop_page_nav ui_edges startup`：262 条，1 条红，即 `test_ui_edges.BatchContinuationTests.test_asset_batch_asks_before_remaking_finished_assets`。
    - 该用例的状态栏被后台续签提示“会员授权续签未成功：登录已失效”覆盖，属测试隔离问题（后台续签读到本机账号状态）。
    - 单独复跑该类 6 条通过。
    - 测试宿主 `_require_login` 为假，R2048 的钩子在测试里不加锁、不写状态栏，与本轮无关。
  - 默认冒烟通过。
- 断言未动。未运行：`--all --safe`、真实界面目测。未 push。
