# R2052 登录框默认记住上次登录的邮箱（功能轮）

轮次类型：功能轮。日期：2026-10-25。

- 需求：登录账号增加记忆功能，默认显示上一次登录的账号，邮箱无需用户再输入。
- 改动：
  - `account_store.save_session` 登录成功写入 `last_email`；`clear_session`（退出登录）保留它；新增 `last_email()`（缺 `last_email` 时回退到会话里的 `email`，兼容升级前已登录的老会话）。
  - `AccountController.last_email()` 供界面读取（替身 store 没有该方法时返回空）。
  - `desktop_account_page._build_login_form`：邮箱框默认填上次的邮箱；账号页与启动登录闸共用这一个表单，两处都生效。从没登录过则仍显示「邮箱地址」占位。
  - 只记邮箱，不记密码。
- 测试：`test_login_gate` 新增 1 条（从没登录过不预填；退出登录后仍预填且令牌已清）。`test_account_page.use()` 每用例先删共用会话文件——该文件各用例共用，退出登录现在会留下 last_email，不删会让后面用例的邮箱框被预填；这是夹具隔离，断言未动。
- 验证：`run_selftests -k account login membership entitlement page_lock update_notice` 141 条全过；默认冒烟通过；`--architecture` 剩 3 条红均与本轮无关（test_agents_md 在 master 同红；test_skill_reference_injection 为本工作树缺未跟踪 skill 文件；test_round_number_continuous 是分支未写状态页的正常现象，合入 master 补记后恢复）。
- 未运行 `--all --safe`、真实界面目测。未 push。
