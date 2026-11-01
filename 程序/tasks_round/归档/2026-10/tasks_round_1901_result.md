# R1901 功能轮：账号页 P2 界面（设备解绑、注销与撤销、账号数据导出）

- **本轮类型**：功能轮。按交接单 `HANDOFF_20261023_P2.md`（task-progress-slow 工作树）在「00 会员账户」页实现 P2 界面；契约见 `说明/账户会员云端设计.md` §3.2。分支 `claude/account-p2-d34b53`，从 master 376c36dc 开出。
- **三问**：
  1. 做了什么：编排层新增设备、解绑、注销、撤销注销、导出五个动作，并抽出公用的租约调用（401 时先续签再重试），兑换也改用它；账号页新增三张卡片，登录表单在冷静期内被拦时提供「撤销注销」。
  2. 怎么验证：新增 18 条测试；跑了选测、受影响冒烟和架构门禁。
  3. 还差什么：在测试服用真实账号走一遍解绑、注销、撤销、导出。

## 改动
- `account_controller.py`：
  - 新增 `_lease_call(call, done, label, *, then=None)`：用本机租约在后台调用接口；没有租约返回 False。遇到 401 `session_invalid` 时用刷新令牌续签一次，再用新租约重试；续签结果表明会话已失效（`SESSION_DEAD`）时清掉本机会话。`then` 在后台线程里处理结果（落盘、清会话），返回结果，不抛异常。
  - `redeem()` 改用 `_lease_call`，行为不变：原有兑换测试全部通过。
  - 新增 `devices(done)`、`unbind(device_id, done, *, current=False)`：解绑的是本机且成功时清本机会话。
  - 新增 `request_delete_code(done)`、`request_deletion(code, done)`：注销申请成功后清本机会话（服务端已吊销全部会话）。
  - 新增 `cancel_deletion(email, code, done)`：用登录验证码撤销注销，不带租约。
  - 新增 `export(target, done)`：拉取导出 JSON（含 `redemptions`），经 `agent.core.save` 写到用户选的路径；写盘失败返回 `write_failed`。内容只写这个文件，不进日志。
- `desktop_account_page.py`（`AccountPageMixin`）：
  - 已登录视图新增三张卡片：
    - **已绑定设备**：点「查看已绑定设备」才联网读取，画页时不发请求。每行显示名称、系统、本机标记、首次和最近使用时间，带「解绑」按钮；列表下显示「已绑 n/3 台，30 天内还可解绑 k 次」。次数用完时按钮禁用，并提示下次可解绑的时间。解绑前弹危险确认框：解绑别的设备后刷新列表；解绑本机后重绘为未登录。
    - **导出账号数据**：用 `file_dialog.save_file` 选保存路径，默认文件名 `漫剧助手账号数据_YYYYMMDD.json`；取消选择则不导出。
    - **注销账号**：先「发送注销验证码」，「确认注销」才可用；确认注销使用 `PrimaryButton` 加 `Tokens.Danger.TButton` 样式（与 `desktop.py` 回收站确认一致），提交前弹危险确认框。成功后重绘为未登录，状态栏显示冷静期截止时间。
  - 登录表单：登录返回 403 `account_pending_deletion` 时，显示「撤销注销」按钮，用当前邮箱和验证码调用 `delete_cancel`（被拦下的登录码不会被消耗）。成功后提示重新发送验证码登录。
  - 确认框和保存路径分别经 `_account_confirm`、`_account_export_path` 注入，测试可以替换。
  - 新增 `device_text()`、`EXPORT_NAME`。只用了 `ui_tokens` 和 `ui_widgets`，没有魔法数字和内联 hex；`desktop.py` 没动。
- 没有新增模块，也没有新增 `json.loads`，`架构统一基数.json`、覆盖率基线和 `runbook.md` 里的模块数都不用刷新。

## 测试（本轮运行）
- `tests/test_account_client.py` 新增 10 条：
  - 客户端：P2 五个接口的方法、路径、请求体；撤销注销不带 Bearer。
  - 编排：
    - 设备列表和解绑别的设备后，会话保持不变；解绑本机后清会话；解绑次数超限时会话保持不变。
    - 租约过期时按「设备 → 续签 → 设备」的顺序重试。
    - 没有会话时五个动作都返回 False，不发请求。
    - 注销验证码错误时保留会话，成功后清会话。
    - 撤销注销用去掉首尾空格的邮箱和验证码。
    - 导出写入所选文件且包含 `redemptions`；导出失败时不写文件；写盘失败返回 `write_failed`。
- `tests/test_account_page.py` 新增 7 条（经 `gui_hidden.py` 运行）：
  - 设备列表与解绑别的设备；解绑本机后退出登录；次数用完时按钮禁用。
  - 注销完整流程；确认框取消时不发请求。
  - 导出：取消选择不写文件，选了路径就写入。
  - 冷静期登录被拦后，出现「撤销注销」按钮，撤销成功后按钮隐藏。
  - 另外修了测试自身的隔离问题：页面测试共用同一个会话文件，新增的已登录用例用 `addCleanup` 清掉会话，避免污染未登录用例。
- `tests.test_account_client` 42 条、`tests.test_account_page` 11 条，全部通过。
- 架构门禁共 394 条。首轮抓到 `test_button_boundary` 报裸 `ttk.Button`，已改为 `PrimaryButton`，复跑按钮、函数长度、复杂度、模块大小 4 个门禁共 33 条，全部通过。剩余 1 failure、1 error 都是既有问题：`test_skill_reference_injection`、`test_agents_md`，原因是本 worktree 缺未跟踪的文件。
- 选测：经 `gui_hidden.py` 运行 `run_selftests.py -k account_entry account_client account_page`，共 56 条，0 个文件有红。改按钮后又单独复跑了 `tests.test_account_page`，11 条通过。
- 受影响冒烟：`smoke_test.py --affected account_controller desktop_account_page`，9 项全过。
- **未运行**：测试服真实账号上的解绑、注销、撤销、导出；全量测试。
- **断言未动**：已有测试的断言一条未改，只在后面追加了新用例。

## 后续
- 在测试服用真实账号走一遍 P2。注销会让账号进入 7 天冷静期，最好用专门的测试账号。
- 交接单里其余的后续项不变：手动页面按钮接入闸门、「质检与交付」导出闸门、正式服上线开关、购买链接。

- **提交**：`R1901: 账号页 P2 界面（设备解绑、注销与撤销、账号数据导出）（功能轮）`，未推送。
