# R2035 合入 codex/wip-R2028 到 master（合并轮）

轮次类型：合并轮。日期：2026-10-25。

- 合入分支 `codex/wip-R2028`（R2028，`fee1119e`：账号补全，含密码登录／注册／找回密码）。master 已前进到 R2031，非快进合并，产生合并提交 `d37fda90`，父提交为 `f76ac43b` 和 `fee1119e`。
- 冲突共 2 个文件：
  - `desktop_account_page.py`：沿用 R2025 的按钮右排并去掉规则小字；已登录视图在按钮后挂 R2028 的设置密码卡片。
  - `ui_tokens.py`：沿用 R2027 删去的 `sidebar_badge_wrap`；`login_gate_width` 取 R2028 的 460。
- 与 R2029／R2031 拆分 `desktop.py` 的改动文件不相交。核对过合并结果相对 `f76ac43b` 只含 R2028 的 12 个文件。
- 合并后验证（在 R2031 之上实跑）：
  - `run_selftests -k account login membership entitlement master_skill_update widget test_ui_edges test_ui_batch6_pages cloud_assets seedream tts_settings pet_models desktop_page_nav lifecycle`：331 条全绿。
  - 默认冒烟 8/8。
  - 架构门禁仅余 `test_full_safe_all_is_required_after_eight_source_rounds`（后台自动补跑）与 `test_round_number_continuous`（R2036 补记后消除）。
- 合入 R2031 之前跑过一次，`test_account_entry::test_account_page_opens_without_project` 在并行池里红过一次；单独跑与重跑都通过，没有复现，原因未查明。
- 冲突处断言未动。
- 未运行：`--all --safe`、真实界面目测、真实邮箱注册。
- 未 push。
