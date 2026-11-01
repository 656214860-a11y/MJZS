# R2027 结果（修复轮）

## 用户反馈
侧栏「00 会员账户」下的红框小字（「试用或会员已到期，请到「00 会员账户」兑换续期」）合入后仍在。

## 原因
这行字是 R2018 加的侧栏到期摘要 `membership_badge`。R2025 的分支不含 R2018，所以 R2025 只删了页首说明，没有删到这行。

## 改动（整块删除侧栏到期摘要）
- `desktop_project_pages.build_account_nav`：删除 `membership_badge` 标签。
- `desktop_login_gate`：删除 `refresh_membership_badge()` 及其两处调用、不再使用的 `tkinter` 导入；模块说明改为只讲登录闸。
- `desktop_account_page._account_changed`：钩子只剩 `recheck_login_gate`。
- `entitlement_service`：删除只供侧栏用的 `expiry_summary()`。
- `ui_tokens.DESKTOP_LAYOUT`：删除 `sidebar_badge_wrap`。
- 到期信息仍在「00 会员账户」页的「当前状态」卡里显示。

## 测试（契约有意变更）
- `tests/test_login_gate.py`：删除 `ExpirySummaryTests`（4 条，被测函数已删）；登录与退出用例里的摘要断言删除，退出用例改为断言侧栏不再有 `membership_badge`。登录闸本身的断言未动。

## 验证
- gui_hidden 定向：login_gate／account／membership／entitlement／ui_tokens 共 111 条通过。
- `smoke_test.py --architecture`：410 条，剩 3 条既有红（agents_md 基准历史文件缺失、round_baselines、skill_reference_injection）；complexity_ratchet 已转绿。
- 未在真实窗口目测。
