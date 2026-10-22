# R1890 功能轮：A1 账号服务端骨架（P0）

- **本轮类型**：功能轮。代码落在**独立仓库** `D:\漫剧服务端`（`main`，提交 `a5b5556`，未推送）；本仓库只改设计文档、待办与本结果文件，未改任何 `.py`、测试、配置或用户数据。队列 ID：优化待办 A1（非 maintenance-queue 条目）。
- **服务端实现**：FastAPI + SQLite（WAL）+ RSA-2048 租约。接口 `/healthz`、`/v1/meta`、`/v1/auth/email/code`、`/v1/auth/email/verify`、`/v1/lease/renew`、`/v1/me`；编号迁移 `0001_init`（up/down）；脚本 `gen_signing_key.py`、`verify_lease.py`（纯 Python 验签，桌面端 `lease_verifier` 的参考实现）、`backup.py`。
- **设计文档同步**（`说明/账户会员云端设计.md`）：§3.2 code 接口不收 `device_id`、renew 须带 `device_id` 且复用旧令牌吊销全部会话、`/v1/me` 以租约作 Bearer、`/v1/meta` 只给 kid；§4.1 新增 `sid` 字段、试用期租约与宽限封顶在 `trial_ends_at`；§10 服务端仓库位置已定。
- **测试（本轮在服务端仓库运行）**：`.venv\Scripts\python -m pytest`（经 `工作流任务\gui_hidden.py`）31 passed。覆盖：注册试用与封顶、年龄/协议必填、邮箱规范化、验证码错 5 次锁定、过期与单次使用、新码作废旧码、邮箱/IP 限流、非法设备、设备上限 3、试用台账防二次试用、试用到期、注销冷静期拦截、刷新轮换与复用吊销、设备不符、刷新过期、租约篡改/过期、版本中间件、`/v1/meta`、参数错误体、迁移 up/down/up、未迁移拒绝启动、独立验签（含篡改与错公钥）、密钥脚本拒绝覆盖、备份恢复演练。另做命令行 `python -m app.db up / down 0 / up` 演练通过。
- **桌面端测试**：本仓库无代码改动，未运行；欠账计数不变。
- **已知**：starlette 对 httpx TestClient 有弃用警告，仅测试依赖，不影响运行。
- **提交**：`R1890: A1 账号服务端骨架落地，设计文档同步实现（功能轮）`，hash 见 git log；未推送。`project_status.md` 待合入 master 时补记。
