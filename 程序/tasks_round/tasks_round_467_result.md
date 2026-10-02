# R467 结构治理轮结果

## 本轮目标

收口内置 Codex 任务书创建入口的统一上下文预算预检，确保超限请求不会先创建本地任务工件或连接 RPC。

## 改动

- `codex_tasks.prepare_task()` 在取得项目路径、任务锁和任何工件路径之前调用 `ensure_request_context(prompt, stage)`。
- `tests/test_workflow.py` 新增回归：超出 96,000 字符限制时，拒绝请求，且不产生 `工作流任务/` 或 `codex_tasks.json`。
- `architecture.md` 明确 L3 的 `workflow_engines` 与 `codex_tasks.prepare_task()` 都必须在启动进程或创建任务工件前执行该预检。

## 验证

- 定向：`tests.test_workflow.WorkflowContextBudgetTests` 与 `tests.architecture.test_platform_process_boundary`，5/5 通过。
- 架构治理：68/68 通过。
- 默认冒烟：8/8 通过。
- 全量安全自检：3,170/3,170 通过，789.2 秒。

## 范围与后续

仅修改 Codex 任务创建的公共 L3 入口及其回归、架构和状态记录；未改动桌面层或其他业务模块。剩余优化项仍包括其他阶段的上下文/预算口径盘点、响应式界面人工验收、遗留 UI 拆分；真实白模上传仍需用户对具体素材授权。
