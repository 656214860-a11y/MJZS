# R1897 功能轮：服务端兑换码（服务端仓库 `D:\漫剧服务端`）

## 三问
- 轮次类型：功能轮。代码全部在服务端独立仓库；桌面仓库只改设计文档、状态页和本结果文件，桌面端源码未动。
- 测试与基线（本轮实跑）：
  - 服务端本地 `pytest`：53 项全绿（经 `工作流任务\gui_hidden.py`），新增 `tests/test_redeem.py` 12 项。
  - 测试服远端：登录、兑换、独立验签（`state=active`，`period_end` 比 `trial_ends_at` 晚 30 天）、重复 409、乱码 400、`/v1/me`、导出全部通过。
  - 服务器上 `gen_redeem new／stats／revoke` 以 `mj` 用户实跑通过；测试批次 `smoke-test` 已作废，明文文件已 `shred`。
  - 桌面仓库未跑测试，未改源码。
- `project_status.md`：轮次头 1897 → 1898。

## 服务端改动（`main` 6b978df、f828040，未推远端；测试服运行 6b978df，f828040 只改 README）
- **迁移 0003 `redeem_code`**：只存 `keyed_hash(salt, 'redeem', 码)`；`redeemed_by` 外键 `ON DELETE SET NULL`。
- **`POST /v1/redeem`**：字段与错误码见设计文档 §3.2。顺延起点为 max(现在, `period_end`, `trial_ends_at`)，试用中付费不吞剩余试用天数，可叠加。
- **`scripts/gen_redeem.py`**：`new <套餐> <数量> <批次>`，明文只输出一次；`stats [批次]`；`revoke <批次>` 只作废未兑换的码。
- **导出**：新增 `redemptions`。
- **断言变更**：
  - `test_ops` 迁移数改为 `[1, 2, 3]`／`[3, 2, 1]`。
  - `test_account` 导出字段集合补 `redemptions`。
  - 两处都是契约有意扩展，断言未弱化。

## 后续
- 客户端账号页加「输入兑换码」：调用 `/v1/redeem`，成功后用返回的 `lease` 替换本机租约。已通知客户端会话。
- 爱发电／淘宝发卡店铺由用户开通。生成第一批正式码时按服务端 README「兑换码」一节操作。
