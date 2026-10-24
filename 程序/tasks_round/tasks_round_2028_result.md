# R2028 结果（功能轮）：账号补全，含密码登录／注册／找回密码、本机校验与错误色提示

## 起因
用户实测 R2018 登录闸，截图里的邮箱填的是 `656214860@qqcom`，提示“邮箱格式不正确”。用户反馈：
- 没有注册入口；
- 收不到验证码；
- 登录邮箱就是服务端的 SMTP 发件账号，界面没有反馈；
- 没有重复账号校验；
- 没有报错；
- 没有密码。

用户要求账号默认用邮箱，手机后续接入，并补全其他缺失的功能。用户裁定的方案是“密码为主，保留验证码”，服务端“测完就部署”。

## 现状结论（改前）
- 截图里的邮箱少了一个「.」。服务端返回 400 `invalid_email`，界面底部那行灰色 Muted 字就是报错，用户没注意到。客户端发码前只查非空，不查格式。
- 服务端日志里，同一邮箱之后的发码（01:49、01:52）都成功了。所以发件账号给自己发信能送达，没有被拦。
- 重复账号本来就有 `identity` 表的 `UNIQUE(kind, value_norm)` 约束。但注册与登录是合一的（验证码首次登录即建号），界面上从来不会出现“已注册”。
- 服务端没有口令，这是原设计（§3.1“不存口令”）。
- 服务端先写码后发信，SMTP 失败时也照样占 60 秒冷却和每小时额度。
- 登录闸容器宽 420px，标签却按 560px 换行，文字被截断。
- 账号请求走 `async_queued`，有别的后台任务时一直停在“正在发送验证码…”。

## 本轮改动

### 服务端
服务端是独立仓库 `D:\漫剧服务端`，提交 `aafa4a0`，已部署到测试服 8.138.223.126。
- 迁移 0007：新增 `user_password` 表；`email_code.purpose` 增加 `register`／`reset`；带 down 脚本。
- 口令哈希挪到 `app/security.py`，与管理员共用 scrypt。强度规则：8–64 位，同时含字母和数字。
- 新接口：
  - `POST /v1/auth/register`；
  - `POST /v1/auth/password/login`：失败统一返回 401 `password_invalid`，没设过口令返回 `password_not_set`，按邮箱和 IP 限流；
  - `POST /v1/auth/password/reset`：吊销该账号全部会话；
  - `POST /v1/account/password`：已有口令时须带原口令。
- 发码接口增加 `purpose`：
  - `register` 遇已注册邮箱返回 409 `email_registered`；
  - `reset` 遇未注册邮箱不发信，但仍返回成功。
- 发信失败返回 503，并撤回本次验证码与限流记录，不再占冷却。
- `/v1/meta` 增加 `features: ['password']`。

### 桌面端
- `account_client.py`：
  - 新增 `register`、`password_login`、`reset_password`、`change_password`；`send_code` 增加 `purpose`。
  - 新增 `valid_email()`，与服务端同一条正则；新增 `password_problem()`。
  - `MESSAGES` 增加 4 个错误码。
  - HTTP 错误时把 `code`、`status`、`retry_after` 放进 `data`。
- `account_controller.py`：
  - 新增对应的 4 个动作，以及带 purpose 的 `request_code`。
  - 重置的是本机正登录的同一邮箱时，清掉本机会话。
  - 修改口令走租约（Bearer）。
- `account_store.py`：会话字段增加 `has_password`。
- `desktop_account_page.py`：
  - 登录表单改为四个视图共用一个邮箱框：密码登录（默认）、注册、验证码登录、找回密码，顶部是“登录 | 注册”切换。
  - 注册视图：邮箱 + 验证码 + 两次密码 + 18 岁勾选。
  - 本机先查邮箱格式、密码强度、两次输入是否一致；错误标在对应输入框上，提示用错误色（`Expired.TLabel`）。
  - 限流时提示“N 秒后可重试”。
  - 服务端不支持口令接口（404）时，自动退回验证码登录。
  - 注册时邮箱已注册，转到密码登录，并提示可以“忘记密码”。
  - 验证码视图拆成模块级 `_login_code_view`，满足函数行数上限。
  - 已登录视图新增“设置／修改登录密码”卡片。
  - `_account_submit` 在后台已有任务时改走独立线程，不在队列里干等。
- `ui_widgets.LineInput`：新增 `mask`，只遮用户输入，不遮占位文字。未传 `mask` 时取 `show`，已有 `show='•'` 的调用方行为不变。同时压缩了 `_set_style`，文件行数 1421，在上限 1425 以内。
- `ui_tokens.py`：`login_gate_width` 由 420 调到 460，新增 `login_gate_wrap`（宽度减两侧 `SPACING['lg']`）。
- `desktop_login_gate.py`：标签和表单按 `login_gate_wrap` 换行，更新了 `LOGIN_GATE_NOTE` 文案。
- `说明/账户会员云端设计.md`：§3.1 数据表、§3.2 接口表同步更新。

### 契约有意变更（断言未动）
- 测试里的样例邮箱 `a@b.c` 改为 `a@b.cn`：客户端现在按服务端规则校验，`a@b.c` 已不合法。
- 验证码登录相关的测试先点「用验证码登录」再操作，因为默认视图已改为密码登录。
- 替身客户端的 `send_code` 调用参数多了 `purpose`。

## 验证（本轮实跑）

### 服务端
- `pytest` 101 条通过。
- 部署输出“已执行：[7]”“已发布 aafa4a0”。
- 只读探测 5/5 OK：meta 含 password、密码登录错误码、少点邮箱 400、弱口令 400、重置码无效。
- `scripts/smoke_remote.py` 需要 `MJ_MAILER=log`，测试服是 smtp 模式，跑不了。这是既有限制。

### 桌面端
- `run_selftests -k account login membership entitlement`：125 条全绿。新增 14 条：客户端 2、控制器 5、页面 7。
- 默认冒烟 8/8。
- `--architecture` 只剩 2 条旧红：`skill_reference_injection`、`agents_md` 性能历史。首轮跑出的两条新红（`_build_login_form` 169 行，上限 150；`ui_widgets` 1433 行，上限 1425）已拆分和压缩修掉，没有抬高任何上限。
- 扩大范围跑 `-k … widget ui_ cloud_assets seedream tts_settings pet_models`：441 条中只有 `test_ui_edges` 与 `test_ui_batch6_pages` 超时。
  - `batch6` 单独直跑 7 条 OK。
  - `test_ui_edges::test_unattended_chain_runs_asset_final_keyframe_in_order` 卡在总控包更新确认框（`master_skill_update.check()` 真联网，发现了新版本）。同一条在 master 上直跑通过（27 秒）。
  - 原因：本分支基于 R2021，缺 R2023 的离线桩 `DRAMA_SUPPRESS_NETWORK`。不是本轮代码导致的。

## 未做／未验证
- 没有用真实邮箱在真机走注册→收信→登录；要请用户用带「.」的邮箱试一次。
- 没跑 `--all --safe`。
- 手机号只在数据模型里预留。
- 本分支落后 master 5 个提交（R2023–R2027）。其中 R2025、R2027 也改了 `desktop_account_page.py`、`desktop_login_gate.py`、`ui_widgets.py` 与相关测试，合入时需要解冲突后重测。
- 回滚：
  - 桌面端：`git revert` 本轮提交。
  - 服务端：`python -m app.db down 6`，再切回 `/opt/mj-server.old`。
