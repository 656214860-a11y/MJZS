# R2046 结果：登录闸登录后账号页仍显示「未登录」（修复轮）

## 现象
用户用验证码登录（启动登录闸）后，内容区显示「当前状态：未登录」和登录表单，状态栏却是绿色的「登录成功」。

## 根因
其实登录已经成功：本机 `private/账户/session.json` 已写入刷新令牌和租约，租约验签通过。服务端给的套餐是 `state=expired`、`plan=none`，正确的显示应为「授权已失效」。

问题出在闸门下面那张「会员账户」页。它是启动时、还未登录时画的。`LoginGateMixin._login_gate_passed` 只拆闸门、写「登录成功」，没有重画这张旧页，旧的「未登录」画面就露了出来。

## 改动
- `desktop_login_gate.py`：`_login_gate_passed` 收尾时，若当前页是 `PAGE_ACCOUNT`，就调用 `show(PAGE_ACCOUNT)` 重画。
- `desktop_account_page.py`：`_build_login_form` 新增 `signed_in()`，登录、注册、验证码登录成功后都经它调用 `on_success`。
  - 只认本机验签后的状态。如果仍是 `SIGNED_OUT`，就留在表单上报错，不跳转，也不报「登录成功」。
  - 这是兜底：`AccountController._accept` 本来已先验签再落盘。
- 测试（新增，没有改动已有断言）：
  - `tests/test_login_gate.py::test_gate_login_redraws_account_page_underneath`
  - `tests/test_account_page.py::test_login_reply_ok_but_still_signed_out_stays_on_form`

## 验证（本轮实跑）
- `run_selftests.py -k test_account_page test_login_gate test_account_entry test_account_client`：83 条，ALL TESTS PASSED。
- 回退两处源码后重跑：新用例红，停在「当前状态：未登录」加登录表单，与用户截图一致；恢复源码后转绿。
- `smoke_test.py --architecture`：只有已知遗留的 3 项红（agents_md、round_baselines、skill_reference_injection），与 R2032 记录一致，与本轮无关。
- 未在真实应用里重新登录验证。
