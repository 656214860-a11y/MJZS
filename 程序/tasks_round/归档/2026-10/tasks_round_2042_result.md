# R2042 结果：test_account_entry 改用临时账号存储（测试隔离轮）

## 问题
R2041 合入后，在主目录跑测试时 `test_account_entry.test_account_page_opens_without_project` 失败。原因是这个用例的 Desktop 用默认的 `AccountController`，会读本机 `程序/private/账户/session.json` 里的真实登录会话。本机已登录时，账号页显示的是已登录视图，测试找不到 `account_login_button`。worktree 里没有这个会话，所以同一条测试是绿的。

## 改动
- `tests/test_account_entry.py`：在 setUpClass 里建好 Desktop 后，注入一个绑定到临时目录的 `AccountController`。做法与 `test_account_page` 一致：用 `_Store(临时路径)`、空的 `_Client()`、固定时钟 `NOW`，`enforce=True`。
- 只改测试，产品代码没动。断言未动。

## 验证（本轮实跑）
- worktree：`run_selftests.py -k account_entry account_page login_gate`，ALL TESTS PASSED。
- 主目录（有真实登录会话）：把改好的测试文件临时复制过去，跑 `run_selftests.py -k account_entry`，ALL TESTS PASSED。跑完已用 `git checkout` 还原主目录，工作区干净。
