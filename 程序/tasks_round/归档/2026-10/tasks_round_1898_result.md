# R1898 功能轮：账号页「输入兑换码」入口

- **本轮类型**：功能轮。服务端会话转达用户需求：服务端 `POST /v1/redeem` 已上测试服（服务端 6b978df；桌面端文档在 R1897，35a6df83），请在账号页加「输入兑换码」入口。契约见 `说明/账户会员云端设计.md` §3.2。分支 `claude/account-redeem`，从 master 35a6df83 开出。
- **三问**：
  1. 做了什么：客户端新增兑换接口、编排、页面入口，并按 plan 显示套餐名。
  2. 怎么验证：新增 8 条测试；跑了选测、受影响冒烟和架构门禁；测试服只读探测。
  3. 还差什么：用真实兑换码完整兑换一次。需要先在测试服登录一个账号，再请服务端会话生成兑换码。

## 改动
- `account_client.py`：
  - 新增 `redeem(lease, code)`，Bearer 租约＋`{"code"}`，码原样提交，归一化由服务端负责。
  - `MESSAGES` 新增 `redeem_invalid`、`redeem_used` 两个错误码的中文提示。
- `account_controller.py`：
  - 新增 `redeem(code, done)`。本机没有租约时返回 False。
  - 兑换成功后，先验签再落盘：用 `_accept(rotate=False)` 只替换租约，`refresh_token` 和邮箱不变。
  - 本机租约过期导致 401 `session_invalid` 时，先续签一次，用新租约重试兑换。续签返回会话已失效时清掉会话。
  - 兑换失败、或返回的租约验签不过，都不改本机会话。
- `desktop_account_page.py`：
  - 已登录视图新增兑换码卡片：输入框、「兑换」按钮、提示行；最长 40 字符，空值不提交。成功后重绘页面，状态栏显示「兑换成功，会员增加 N 天」。
  - 套餐名改由 `plan_text()` 按 `plan` 显示：monthly 为月度会员，quarterly 为季度会员，yearly 为年度会员；state 为 expired 时一律显示「已到期」。
  - 修正一处顺序：登录、退出、兑换完成后先重绘页面再写状态栏，否则重绘时页面说明会把状态栏覆盖掉。

## 测试（本轮运行）
- 经 `gui_hidden.py` 运行 `tests.test_account_client`、`tests.test_account_page`、`tests.test_account_entry`，共 39 条通过，其中本轮新增 8 条：
  - 客户端：请求路径、Bearer 头、码原样提交；409 和 400 的错误码映射。
  - 编排：
    - 兑换成功后换租约、保留刷新令牌，闸门随之放行。
    - 兑换失败或返回坏租约时，会话保持不变。
    - 租约过期时按 兑换 → 续签 → 兑换 的顺序重试。
    - 续签也失效时清掉会话；之后再兑换直接返回 False。
  - 页面：已登录视图里兑换后，套餐变为「季度会员」，状态栏显示天数；`plan_text` 的各分支。
- `smoke_test.py --affected account_client account_controller desktop_account_page`：9 项全过。
- 架构门禁共 394 条，剩 1 failure、1 error，都是既有问题：`test_skill_reference_injection`、`test_agents_md`，原因是本 worktree 缺未跟踪的文件。
- 测试服探测：用无效租约调 `/v1/redeem` 返回 401 `session_invalid`，说明接口已上线、鉴权正常。
- **未运行**：用真实兑换码完整兑换一次；全量测试。
- **断言未动**：已有测试的断言一条未改。只扩展了 `tests/test_account_client.py` 里的 `_Client` 替身，让它支持按顺序返回多次结果。

## 后续
- 导出数据新增的 `redemptions` 字段，等 P2「数据导出」界面做时一起展示。
- 爱发电／淘宝的购买链接要不要放进账号页，待用户决定。

- **提交**：`R1898: 账号页「输入兑换码」入口（功能轮）`，未推送。
