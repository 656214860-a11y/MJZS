# R2066 修复并发续签把正常会话清掉导致「突然退出登录」（修复轮）

轮次类型：修复轮。日期：2026-10-25。

- 现象：正常使用中突然回到登录页。服务端日志（`mj-api`）13:01:51 同一秒有两个 `POST /v1/lease/renew`，一个 200、一个 401；本机 `private/账户/session.json` 的令牌与租约被清空。
- 原因：服务端每次续签换新刷新令牌、旧令牌立刻作废。窗口回前台续签（R2064）、12 小时定时续签、带租约请求遇到租约过期的自动续签可能同时用同一个旧令牌发出；第二个被拒（`session_invalid`），`account_controller` 随即 `clear_session`。
- 修复（`account_controller.py`）：新增 `_renew_lock` 与 `_renew_once`。
  - 续签持锁串行；拿到锁后重读本机令牌，与本次所用不同说明别处刚续过，直接用现成的新会话，不再拿旧令牌请求。
  - 会话失效只在本机令牌仍是本次所用令牌时才清；真正被吊销的会话仍照常清。
  - `renew()` 与 `_lease_call` 的自动续签共用 `_renew_once`。
- 新增 `tests/test_renew_concurrency.py`（3 条）：两个续签同令牌并发只请求一次且不清会话；租约过期的带租约请求与续签并发，换新租约重试成功；真失效仍清。修复前 2 条失败（请求 2 次），修复后全过。
- 验证：`run_selftests -k test_account test_membership test_renew test_login_gate test_background_checks` 全过；断言未动。
- 未运行：`--all --safe`、架构门禁、真实界面目测。未 push。
