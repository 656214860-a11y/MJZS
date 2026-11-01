# R2054 邮箱后缀下拉 + 全部密码框带显示/隐藏图标（功能轮）

轮次类型：功能轮。日期：2026-10-25。基于 codex/wip-R2052（其上 master 已是 R2053 合并轮）。

- 邮箱框：新模块 `account_inputs.py` 的 `EmailInput`——左边填账号，右边是可下拉、可手改的后缀（@qq.com／@163.com／@126.com／@gmail.com／@outlook.com／@foxmail.com／@hotmail.com／@sina.com／@icloud.com／@yeah.net，默认 @qq.com）。`get()` 返回拼好的完整邮箱；整串地址粘进账号框或 `insert` 时自动拆开，所以“上次登录的邮箱”预填（R2052）与既有测试照常工作。账号页与启动登录闸共用的登录表单已换用。
- 密码框：`PasswordInput`——右侧一个图标按钮（👁 遮挡中／🙈 明文显示中）切换明文。已用于账号表单全部 8 个密码框（登录、注册两个、找回两个、修改密码三个），并覆盖其余 API Key 密码框：`cloud_assets`（Comfy Key）、`seedream_settings`、`tts_settings`、`pet_models_ui`（模型管理密钥框，保持 `*` 遮挡字符）。未改：`cloud_video` 的 Key 框（它自带“临时显示/定时遮回”机制且测试按 `configure(show=)` 约束，另议）。
- `ui_widgets.LineInput` 新增公开 `set_mask()`（+4 行，ui_widgets 上限 1125 持平，没抬高）。
- 登记：`tests/architecture/_layers.py` 登记 `account_inputs` 为 L4；`覆盖率基线.json` 新增一行（总数 +1）；`runbook.md` §11 口径 323→324、273→274。
- 测试：新增 `tests/test_account_inputs.py`（6 条：后缀拼接与下拉项、整串地址拆分、错误标记；密码框图标切换明文、事件/错误转发）。既有断言未动。
- 验证：`run_selftests -k account login account_inputs pet_settings pet_models cloud seedream tts model_pool` 388 条全过；默认冒烟通过；`--architecture` 剩 3 条与本轮无关的红（test_agents_md 在 master 同红；test_skill_reference_injection 为本工作树缺未跟踪 skill 文件；test_round_number_continuous 是分支未写状态页的正常现象）。
- 未运行：`--all --safe`、真实界面目测（图标在 Windows 上的实际渲染、后缀下拉的宽度需目测）。未 push。
