# R1957 修复轮：去掉侧栏「00 会员账户」的状态后缀

## 原因
用户反馈：侧栏「00 会员账户（未登录）」后缀多余，窄侧栏里还被截成「（未登」。会员状态已在账号页状态卡里显示。

## 改动
- `desktop_account_page`：删除 `refresh_account_badge` 及三处调用（被拦、续签 tick、画账号页）；按钮文字固定为 `ACCOUNT_TITLE`。
- `entitlement_service.membership_view`：去掉只给侧栏后缀用的 `badge` 字段，返回 `{lines, level}`。

## 测试（契约有意变更）
- `test_account_page`：原断言按钮含「（未登录）」「（已到期）」，改为断言按钮文字等于 `ACCOUNT_TITLE`（更严格）。
- `test_membership_view`：`badge` 断言随字段删除改为断言 `level`；其余断言未动。

## 验证
- `smoke_test.py --affected desktop_account_page entitlement_service`（经 `gui_hidden.py`）208 条全绿，含 `test_account_page`、`test_membership_view`。
- 未跑架构门禁、smoke 默认集与 `--all --safe`；未在真实窗口目测。
