# R2041 结果：合入 codex/wip-R2040 到 master（合并轮）

## 内容
- 把 R2040（`0d6f67ec`）合入 master（`ddbe58d2`，已含 R2038／R2039 的三虎云朵框精简）。R2040 把账号页的改密、设备、导出、注销改成了底部按钮＋弹窗。
- 两边改动的文件不重叠，自动合并，没有冲突。

## 验证（在主目录对合并结果实跑）
- `run_selftests.py -k account login_gate membership pet_cloud`：只有 1 条红，即 `test_account_entry.test_account_page_opens_without_project`，与本轮无关：
  - 原因：主目录 `程序/private/账户/session.json` 有本机真实的登录会话，这条用例没有隔离账号存储，看到的是已登录视图，所以找不到 `account_login_button`。
  - worktree 里没有这个会话，同组用例全绿。R2040 没有改登录表单。
  - 后续：给 `test_account_entry` 注入临时账号存储，不再读真实会话。
- worktree 内 R2040 的验证记录见 `tasks_round_2040_result.md`。
