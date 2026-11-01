# R411 兼容/平台适配轮结果

## 目标

将 Codex/Claude 的可见交互 CLI 启动收敛到 Windows 平台进程边界，同时保留既有 API 回退条件。

## 改动

- `workflow_engines.py`：交互式 Codex/Claude CLI 经 `platform_tools.launch_windows_app()` 启动；仅适配器包装的实际 `OSError` 继续触发 API 回退，平台不支持或程序缺失直接保留可操作错误。
- `tests/test_workflow.py`：覆盖交互启动经平台边界传递可执行文件、命令和工作目录。
- `tasks_round/tasks_round_182_optimization_checklist.md`、`project_status.md`：登记本轮进展并推进至 R412。

## 验证

- `python -m unittest tests.test_workflow.WorkflowContextBudgetTests`：3/3 通过。
- `python smoke_test.py --affected workflow`：9/9 通过，工作流定向 79/79 通过。
- `python smoke_test.py`：8/8 通过。

## 自审

仅替换交互 CLI 的最终启动边界；未改变任务文件、Codex/Claude 参数、进程台账、API 回退配置或用户项目数据。功能轮越界依赖检查通过。
