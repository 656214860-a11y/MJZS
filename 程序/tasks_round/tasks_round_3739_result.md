# R3739 结果：B 安全与数据边界取证轮（任务书执行轮）
<!-- round-evidence: {"commit_base": "455549e1", "credential_hits": 0, "evidence_sha256": "bb258ef545ddd455", "exit": 0, "failed": 0, "passed": 99, "round": 3739, "tests": "run_selftests.py -k account_client account_security account_offline account_inputs"} -->

- 轮次类型：任务书执行轮（B 维安全与数据边界取证）。纯取证＋文档轮，无产品代码改动。
- 是否跑测试：跑了。桌面侧 `run_selftests.py -k account` 128/128 通过（7 个测试文件，含 test_account_security/test_account_client/test_account_offline/test_account_page/test_account_entry/test_account_inputs/test_account_background_checks，GUI 隐藏桌面执行）；服务端 `D:\漫剧服务端` 全量 pytest exit=0（探针内嵌执行）；探针本身对测试服 `https://8.138.223.126` 完成 49 项 API/协议级实测：48 通过 / 0 失败 / 1 跳过（admin 8443 公网不可达，属外部限制如实记录）。
- 积压是否下降：是——验收台账 B 项由「待验」转「通过」；SSH/管理面子项按 §0 既定口径保持未测归 D 轮复测。

## 1. 三问

1. **什么类型轮**：任务书《桌面与云服务架构及全链路验收任务书》执行顺序第 4 步「B 安全与数据边界」——有效/失效会话、权益拒绝、管理面访问限制、限流、敏感字段遮盖、有效配置核对，客户端表现／服务端状态／配置版本三列对照。
2. **是否跑测试**：跑了——桌面账号域 128/128、服务端全量 pytest 绿、探针 48/49（1 SKIP）。
3. **积压是否下降**：是——B 项证据链闭合；无新增欠账。

## 2. 取证方法（复用现有，零新增产品依赖）

- `scripts/acceptance_security_probe.py`（本轮新增）：对测试服做 TLS 钉证书握手、版本闸门、认证面、只读 GET、应用层/ nginx 层限流、管理面端口、客户端离线验签与权益状态机核验；证据脱敏导出 `tasks_round/evidence/R3739/security_probe.json`。
- 真实会话边界：`D:\漫剧制作助手\程序\private\账户\session.json` 仅用于只读 GET（`/v1/me` `/v1/devices` `/v1/providers` `/v1/account/export`）与一次无效兑换码拒绝；**不调用** renew/logout/delete-*/口令接口——刷新令牌一次一换，并发续签触发重用检测会吊销真实会话（`domain/account_client.py` 模块说明）。
- 唯一写操作：`POST /v1/auth/email/code`（login 用途、一次性 `r<ts>b@example.invalid` 假邮箱）验证重发限流；服务端对未注册邮箱同样发码是设计行为。
- 证据脱敏：uid/sid/did 只留 sha256 前 12 位前缀；邮箱本地段遮盖；租约/刷新令牌/口令哈希/IP 不落盘；响应体只记结构与键名。

## 3. 实测结果（49 项明细见 security_probe.json）

### 3.1 TLS 与有效配置

- 对端证书 DER 与客户端内置 `PINNED_CERT` 逐字节一致；TLSv1.3 / TLS_AES_256_GCM_SHA384；HSTS＋X-Content-Type-Options 齐备；`/docs` `/openapi.json` `/redoc` 生产态 404。
- `/v1/meta`：`api_version=1`、`min_client_version=0.0.0`、`kids=['k2026a']`、`features=['password']`；服务端仓库 HEAD `14602b4`（与 R3707 基线一致）。
- 客户端 `CLIENT_VERSION=0.7`；真实 `account_client.meta()` 经 `platform_tools.open_https`＋钉证书上下文调用成功。
- 缺 `X-Client-Version` 与畸形版本均 `400 client_version_required`；`min=0.0.0` 下 426 分支按配置不可达（`app/main.py:119-120` 代码路径＋服务端单测覆盖）。

### 3.2 会话有效/失效

- 有效：真实租约 `GET /v1/me` 200（`status=active`、`subscription.state=active plan=monthly`、设备 1/3）；devices/providers/export 均 200。
- 失效：无令牌/垃圾令牌/空 Bearer/签名篡改/payload 篡改 → 全部 `401 session_invalid`。
- 本机：`session.json` `_mac` DPAPI 完整性 `session_integrity.verify` 通过（只读，不建密钥）；租约验签 kid=k2026a ∈ meta kids；离线 evaluate → `valid usable=True`。

### 3.3 权益拒绝与敏感字段

- `POST /v1/redeem` 无效码 → `400 redeem_invalid`（不改账号状态，仅落服务端自身审计/限流事件）。
- 四个只读接口响应体扫描：无 `pw_hash/password_hash/refresh/token/secret/api_key/fingerprint/ip_hash` 字段；`member_view` 不含供应商地址与凭据。
- 客户端 `_masked`：邮箱与 JWT 三段（各≥24 字符）全部遮盖为 `[已隐藏]`/`[邮箱已隐藏]`。
- 离线状态机夹具：valid/grace/expired/错设备/垃圾 → valid/grace/locked/signed_out/signed_out；阶段闸门免费段放行、付费段拦截。

### 3.4 管理面与限流

- 80→301 HTTPS；8000/8001/8443 公网探测字节后连接被 RST（本机透明代理特征，与 SSH 22 同——裸 connect 假通、发数据即重置）。
- 管理面 8443 TLS 握手不可达 → 记 SKIP；Host 白名单（`admin.py:193-213`）、登录会话门、2r/s 限流（`deploy/nginx-mj.conf:54-71`）由服务端 pytest（test_admin.py 等全绿）与代码路径覆盖。「管理面公网不可达」本身即暴露面限制生效的证据。
- 应用层限流：同邮箱重发 → `429 too_many_requests + retry_after`；非法邮箱 `400 invalid_email`；>16KB body `413`（nginx 先于应用）。
- nginx 层限流：45 连发 `/healthz` → 11 个非 200（503），回充后 `/v1/meta` 恢复 200。

## 4. 测试与基线

- `run_selftests.py -k account`：7 文件 128 用例 0 失败（GUI 隐藏桌面，等待锁约 4 分钟后正常执行）。
- 服务端 `pytest tests -q`（`D:\漫剧服务端\.venv`）：exit=0。
- 默认冒烟/架构门禁/全量安全自测：本轮未声明（纯取证＋文档，无产品代码改动；合入 master 前按 §5 补跑）。

## 5. 阻塞与未测项（如实登记）

- admin 8443 Host 白名单实测、journalctl 取码、异地备份恢复：SSH/管理端口公网不可达（§0 既定环境约束），归 D 轮复测，不视为 B 项失败。
- 426 过旧版本拒绝：部署 min=0.0.0 按配置不可达，代码路径与单测覆盖已核对。
- 探针首版两处探针自身缺陷已修正（裸 connect 被透明代理假通 → 改协议级探测；session.json 路径漏 `程序\` 段 → 已修正并复跑全绿）。

## 6. 下一步（自动续跑）

- R5（C 发布回滚）：distribution_build 制品→干净副本安装/升级/打开/失败回滚演练，产物摘要与版本兼容核对。

## 7. 变更文件

- `程序/scripts/acceptance_security_probe.py`（新增：B 维取证探针）
- `程序/tasks_round/evidence/R3739/security_probe.json`（49 项脱敏证据）
- `程序/tasks_round/桌面与云服务验收台账.md`（B 项状态与取证记录）
- `程序/tasks_round/tasks_round_3739_result.md`（本文件）

## 8. 提交

- 见文末 `round-evidence` 头与 git 提交回执（`commit_round.py` 自动生成 `evidence/R3739.json` 凭据并盖章本文件）。

---
*R3739 · 桌面与云服务架构及全链路验收任务书 · B 安全与数据边界取证轮*
*下一动作：R5 开始 C 维发布与回滚演练*
*基线：桌面账号域 128/128、服务端 pytest 全绿、探针 48/49（1 SKIP=外部不可达如实记录）；冒烟/架构/全量本轮不声明*
*恢复：读本文件＋验收台账 §3＋`scripts/acceptance_security_probe.py --help`；证据在 `tasks_round/evidence/R3739/`*
*注意：admin 8443/SSH 22/8000/8001 公网不可达为本机出口透明代理特征，非服务端缺陷；真实会话全程只读，未触发令牌轮换*
