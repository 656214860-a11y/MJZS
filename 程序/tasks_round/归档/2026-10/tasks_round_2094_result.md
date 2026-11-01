# R2094 自检不联网：account_client 认 DRAMA_SUPPRESS_NETWORK，钉住自检不碰真实账号会话（修复轮）

轮次类型：修复轮。日期：2026-10-30。分支 `claude/account-offline-tests`，基于 master `0a4c4e46`（R2091）。

- 本轮运行：worktree 里经 `gui_hidden.py` 跑 `run_selftests -k test_account_offline test_account_client test_account_security test_renew_concurrency test_login_gate test_membership_refresh_on_view test_account_page test_account_entry test_account_background_checks test_page_lock test_update_notice test_master_skill_update`，全过（新增 4 条）；在补齐 SKILL 子模块的临时目录里，默认 `smoke_test.py` 8/8 通过。未运行 `--all --safe`，由提交后的后台全量补跑。
- 反证：把新加的判断临时改成 `if False:`，`test_account_offline` 4 条中 2 条失败；已还原。
- 断言未动，已有测试与白名单都未改。`project_status.md` 债务未减少：该问题此前未登记为待办。

## 问题

用户反馈「每次重启应用都要重新登录」。原因：

1. 测试里构造的真实 Desktop 用默认 `AccountController`，读本机 `private/账户/session.json`，调用真实 `account_client`。
2. R2064 起 `<FocusIn>` 与 `refresh_membership_view` 在 `renew_due(60)` 满足时静默续签；新 Desktop 的 `last_renew_at` 为 0，首次聚焦就续签。
3. `account_client` 不认 `DRAMA_SUPPRESS_NETWORK`（此前只有 `master_skill_update._fetch` 认）。
4. 提交后的后台全量是多进程并行，多个进程拿同一刷新令牌续签，服务端令牌重用检测吊销整条会话；客户端收到 `session_invalid` 清掉本机会话，下次启动出登录闸门。
- 探针（替换 `renew` 不联网）：`test_idea_chat.BubbleLayoutTests` 24 条用例里续签 6 次，令牌 sha1 前缀与本机真实令牌一致。

## 修复

1. `account_client.request()`：未注入 `opener` 且设置了 `DRAMA_SUPPRESS_NETWORK` 时，直接返回 `SystemError`，`data={'code': 'network', 'detail': 'suppressed'}`，不调用 `platform_tools.open_https`。常量 `SUPPRESS_NETWORK_ENV` 与 `master_skill_update` 同名。显式注入 `opener` 的测试不受影响。
2. `network` 不在 `SESSION_DEAD` 里，续签失败只保留旧会话、等下次，不会清会话。
3. 新增 `tests/test_account_offline.py`：
   - `run_selftests.py` 设置该开关；
   - 开关打开时 `renew`／`meta`／`me`／`devices` 返回 `network`，`open_https` 一次未调用；
   - 注入的 `opener` 照常使用；
   - 真实 `account_store`（临时路径）＋默认客户端续签后，令牌与租约原样保留。

## 未处理

- 用户本机已被吊销的会话需要重新登录一次；之后自检不再碰它。
- `test_leak_teardown`（第 3 轮 after 计数 7，期望不超过 6）属时序波动，本轮未处理。
- 未 push。
