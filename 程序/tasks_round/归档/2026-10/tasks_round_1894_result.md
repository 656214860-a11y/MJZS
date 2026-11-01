# R1894 功能轮：服务端 P2 完成并部署测试服（服务端仓库 `D:\漫剧服务端`）

## 三问
- 轮次类型：功能轮。代码改动全在服务端独立仓库 `D:\漫剧服务端`，桌面仓库只改设计文档和本结果文件，桌面端源码一行未动。
- 测试与基线：
  - 服务端：本地 `pytest` 41 项全绿（经 `工作流任务\gui_hidden.py`），新增 `tests/test_account.py` 10 项。
  - 远端：`scripts/smoke_remote.py` 端到端对测试服全通过。
  - 桌面仓库未运行测试，因为没有改桌面端源码；全量欠账不变。
- `project_status.md` 欠账：本轮不改状态页，留给 master 上下一轮文档轮同步。

## 服务端改动（`main` 8cfc3d3、46df7ae、cd2323e，未推远端）
- **P2 接口**：`GET/DELETE /v1/devices`、`POST /v1/account/delete-code`、`/delete-request`、`/delete-cancel`、`GET /v1/account/export`。字段与错误码见设计文档 §3.2。
- **迁移 0002**：`email_code.purpose`（`login`／`delete`），登录码不能确认注销。前向和回滚由 `test_migration_up_down_up` 覆盖。断言只按迁移数量改为 `[1, 2]`／`[2, 1]`，没有弱化（契约有意变更）。
- **鉴权收紧**：Bearer 租约在设备解绑、账号进入冷静期后立即失效。原来轮换后旧 sid 的租约在解绑后仍可用，这个缺口已补上。
- **`scripts/purge.py`**：冷静期到期账号物理删除，`trial_ledger` 保留，注销后重注册不再给试用。同时清理过期验证码、限流记录、会话，审计日志按 90 天裁剪。
- **`MJ_MAILER=log`**：测试服验证码写入 journald。
- **`deploy/`**：`deploy.sh`、`server_setup.sh`、`mj-api.service`、`nginx-mj.conf`、备份与清理 timer、`mj.env.example`、`pubkeys/`（租约公钥与 IP 自签证书，均为公开内容）。

## 部署与验证（测试服 `8.138.223.126`）
- **系统加固**：
  - SSH 只允许密钥登录：`PasswordAuthentication no`、`PermitRootLogin prohibit-password`。用户在控制台重置密码时会把口令登录重新打开，本轮已再次关闭。
  - 服务以系统用户 `mj` 运行。私钥 600，环境文件 root:mj 640。
- **外网探测**：
  - 80 返回 301 跳 443。
  - 443 用钉住的证书校验通过。
  - 8000 外网连接超时，只监听 127.0.0.1。
- **端到端冒烟（服务端仓库 `scripts/smoke_remote.py`）**：依次验证发码、登录、独立验签、`/v1/me`、设备、导出、续期、旧令牌复用后整链吊销、注销申请、冷静期 403、撤销、恢复登录，全部通过。
- **定时器**：备份和清理各手动触发一次，均成功，备份文件已生成。
- **重启**：重启后 `mj-api`、`nginx` 和两个 timer 全部自动拉起，外网 `/v1/meta` 正常。

## 说明
- 改用 nginx 而不是计划里的 Caddy：Caddy 不在官方源里，从 GitHub 下载也不通。nginx 来自 `alinux4-updates` 官方源。
- 备案通过后的切换步骤见服务端 README 的“备案通过后切域名”：DNS、certbot（PyPI 镜像）、nginx 配置、`MJ_MAILER=smtp`。
- 已把接口变更、测试地址、证书和公钥路径通知客户端会话（`local_37064e56…`）。
