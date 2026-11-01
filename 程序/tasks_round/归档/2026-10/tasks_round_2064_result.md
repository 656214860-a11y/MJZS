# R2064 点进会员账户、窗口回前台时静默续签（功能轮）

轮次类型：功能轮。日期：2026-10-25。

- 起因：后台给账号“顺延 5 天”后应用不刷新。到期信息在本机租约里，原先只有每 12 小时的定时续签才会读到服务端的新值。
- 改动：
  - `account_controller.py`：新增 `RENEW_VIEW_INTERVAL = 60`；`renew_due(interval)` 可传更短的间隔，默认仍是 12 小时。
  - `desktop_account_page.py`：新增 `refresh_membership_view`。间隔不足 1 分钟则跳过，否则静默续签；只有到期信息变了且当前就在账号页时才重画，不会冲掉正在输入的兑换码。
  - `desktop_page_nav.go_page`：点进“00 会员账户”时调用它。
  - `desktop.py`：主窗口 `<FocusIn>` 绑定同一个方法，只响应窗口本身的事件。
- 续签失败仍然静默，保留旧租约，下次再试。
- 新测试 `tests/test_membership_refresh_on_view.py`（5 条）。
- 测试夹具同步：`tests/test_account_page.py` 的 `use()` 把控制器的 `last_renew_at` 设为 `NOW`，当作刚续过，各用例照旧只数自己的请求。断言未动。
- 验证：`run_selftests -k account login membership page_lock desktop_compact desktop_page_nav ui_edges startup`，282 条，0 红。
- 未运行：`--all --safe`、真实界面目测。未 push。
