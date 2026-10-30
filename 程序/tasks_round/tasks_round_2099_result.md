# R2099 合入 claude/account-offline-tests（R2094：自检不联网，不碰真实账号会话）到 master（合并轮）

轮次类型：合并轮。日期：2026-10-30。把 `claude/account-offline-tests` 的 R2094（`2cdc8378`）以 `--no-ff` 合入 master `29bf4eb3`（R2093），无冲突。

- 合入内容：`account_client.py`（未注入 `opener` 且设置 `DRAMA_SUPPRESS_NETWORK` 时直接按 `network` 失败返回，不联网）、新测试 `tests/test_account_offline.py`、`tasks_round/tasks_round_2094_result.md`。
- 本轮运行（主检出，合并后未提交状态，经 `gui_hidden.py`）：`run_selftests -k test_account_offline test_account_client test_account_security test_renew_concurrency test_login_gate test_membership_refresh_on_view test_account_page test_account_entry test_account_background_checks test_page_lock test_update_notice test_master_skill_update` 全过；默认 `smoke_test.py` 8/8 通过。未运行 `--all --safe`，由提交后的后台全量补跑。
- 断言未动。`project_status.md` 只更新头部当前轮次；债务未减少（该问题此前未登记为待办）。
- 本机已被服务端吊销的账号会话需用户重新登录一次。
- 未 push。
