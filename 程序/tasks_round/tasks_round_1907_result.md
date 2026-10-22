# R1907 功能轮：刷新令牌复用演练脚本

## 三问
- 轮次类型：功能轮（开发者工具）。产品源码未改。
- 测试：经 `工作流任务\gui_hidden.py` 跑 `unittest tests.architecture.test_static_hygiene tests.test_dev_entry`，7 条 OK。脚本在主仓库无登录会话时实跑一次，输出「没有刷新令牌」，退出码 2。未连测试服实跑续签。全量自检未运行。
- `project_status.md`：轮次头 1907 → 1908。

## 改动
- 新增 `scripts/drill_refresh_reuse.py`：用同步 `submit` 构造 `AccountController`，调一次 `renew()`。成功时像助手一样写回新刷新令牌；会话失效时像助手一样清会话。只打印结果码与本机会话是否还在，不打印令牌。未登记到 `scripts/dev.py`（一次性手动演练工具）。
- 最初放在 `工作流任务\`，该目录被 `.gitignore` 忽略；用户选定移到 `程序\scripts\` 提交。

## 演练步骤（待用户执行）
1. 助手里登录测试账号，完全退出助手（含托盘）。
2. 在 `程序\private\账户\` 下：`session.json` 复制为 A.json → 跑脚本（预期续签成功）→ 复制为 B.json。
3. A.json 放回 session.json 再跑：预期 `session_invalid`（旧令牌复用触发吊销全部会话）。
4. B.json 放回再跑：预期仍是 `session_invalid`，证明新会话也被吊销。
5. 管理后台「审计」页应有 `refresh_reuse`；助手账户页应要求重新登录；删除 A.json、B.json（含明文令牌）。
