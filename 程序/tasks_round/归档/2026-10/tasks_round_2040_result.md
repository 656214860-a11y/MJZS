# R2040 结果：账号页低频功能改为底部按钮＋弹窗（修复轮）

## 需求
把「修改登录密码」「已绑定设备」「导出账号数据」「注销账号」做成页面底部的按钮，点开后在弹窗里操作。以后新增的低频账号功能，也优先做成这种弹窗按钮，以简化页面布局。

## 改动（`desktop_account_page.py`）
- **新增「账号管理」卡片**：新增 `_account_tools_card`，放在页面最底部，一行 4 个按钮：
  - 设置登录密码／修改登录密码，名称按账号是否已有密码切换；
  - 已绑定设备；
  - 导出账号数据；
  - 注销账号。
  - 以后新增低频功能，在 `tools` 元组里加一项即可，docstring 已写明这条约定。
- **弹窗机制**：`_account_open_dialog` 用统一弹窗骨架 `BaseDialog`（模态，带「关闭」），同一时间只开一个；`_account_close_dialog` 负责关闭。
- **四个功能的改动**：原来的 4 个卡片构建函数改为向弹窗里画控件：`_account_password_form`、`_account_devices_form`、`_account_export_form`、`_account_delete_form`。业务流程不变，具体差异：
  - 保存密码、导出、确认注销这三个按钮放到弹窗底部动作区，确认注销仍是危险样式；
  - 设备列表在打开弹窗时自动读取，原按钮改为「刷新」；
  - 改密成功、注销申请成功、解绑本机成功后，先关弹窗再刷新页面。
- **二次确认**：`_account_confirm` 的确认窗挂在账号弹窗上，关闭后把输入锁收回给账号弹窗。

## 测试（`tests/test_account_page.py`）
- 契约有意变更：各用例先用 `open_tool(key)` 点开弹窗，再按原步骤操作。断言未动。
- 原来手动点「查看已绑定设备」的 3 处，改为打开弹窗时自动读取，调用序列断言不变。
- 改密用例补了 3 个断言：保存后弹窗关闭；按钮名变为「修改登录密码」；重新打开后要求填原密码。
- 新增 `test_low_frequency_tools_are_bottom_buttons_opening_dialogs`，检查 4 个按钮的文字、页面上不再出现注销说明和注销验证码框、每个按钮都能打开同名弹窗。

## 验证（本轮实跑）
- `run_selftests.py -k account login_gate membership`：ALL TESTS PASSED，其中 test_account_page 共 22 条。
- `smoke_test.py --architecture`：一共 410 项，有 3 项已知遗留红，与本轮无关：
  - agents_md
  - round_baselines
  - skill_reference_injection
- 未做：没有在实机界面上目测弹窗的外观。
