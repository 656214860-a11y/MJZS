# R1903 修复轮：test_copy_rules 两条红（勾选框文字过长、旧写法「＋ 新建项目」）

- **本轮类型**：修复轮。这两条失败是「界面UI优化续做：调色板统一方案」会话在 R1900 全量中发现的，用户要求转交本端修复。
- **三问**：
  1. 做了什么：修了两处文案，见下文「改动」。
  2. 怎么验证：见下文「测试」。
  3. 还差什么：主仓库全量由调色板会话补跑。

## 改动

- `desktop_account_page.py` 登录表单（对应 `test_names_stay_short_enough_to_read`）：
  - 勾选框原文「我已年满 18 周岁，并同意用户协议与隐私政策（首次注册必选）」共 29 字，超过按钮名上限 16 字，改为「已满 18 周岁并同意协议」。
  - 完整说明「首次注册必选：确认已年满 18 周岁，并同意用户协议与隐私政策。」移到勾选框下方的提示行（`Muted.TLabel`），用户能读到的信息没有减少。
- `desktop_project_pages.py:257` 项目列表空状态（对应 `test_every_action_keeps_only_its_one_name`）：「关闭此窗口后点「＋ 新建项目」开始」改为统一写法「+ 新建项目」。
  - 这处旧写法来自 543819b3（2026-10-22），不在账号模块里。报错片段紧挨账号 HTTP 客户端，是因为拼接全文时这两个文件正好相邻。

## 测试（本轮运行）

- 经 `工作流任务\gui_hidden.py` 运行 `run_selftests.py -k copy_rules account_entry account_client account_page ui_batch6_pages`：77 条全部通过，0 个文件有红。
- **未运行**：全量测试，由调色板会话在主仓库补跑。
- **断言未动**：`tests/test_copy_rules.py` 与账号相关测试一行都没改。
