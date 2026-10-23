# R1955 功能轮：会员状态可见性补强

## 范围
- `entitlement_service`：新增纯函数 `days_left`、`membership_view`，输出 `{lines, level, badge}`；覆盖未登录、试用／会员剩余天数（≤3 天为 warn）、到期（含到期日期与兑换码指引）、离线超宽限、时钟异常。
- `desktop_account_page`：账号页状态卡下方按 level 显示文案（`Warn.TLabel`／`Expired.TLabel` 两个新样式，用现有 `warning_text`／`danger_text` 令牌）；侧栏「00 会员账户」按钮后缀徽标（未登录／剩N天／已到期／时间异常），在画页、续签 tick、被拦时刷新。
- `account_controller.now()`；兑换码购买渠道暂用文案“请联系发放兑换码的渠道”，渠道确定后再做按钮。
- 被拦提示沿用状态栏（本轮未新增弹窗）。

## 验证
- `run_selftests.py -k account membership_view update_notice`（经 `gui_hidden.py`）全绿；新增 `tests/test_membership_view.py` 5 条、`test_account_page` 1 条。
- 架构目录 394 条：3 红为既有（`test_agents_md` 1、`test_skill_reference_injection` 1 因 worktree 缺技能目录、`test_round_number_continuous` 随本结果文件补齐）。断言未动。未跑 smoke 与 `--all --safe`；未在测试服手工验证。
