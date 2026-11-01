# R406 性能/资源轮结果

## 目标

补齐交互式阶段引擎的请求上下文预算门禁。

## 改动

- `workflow_engines.py`：`launch_interactive()` 在创建 Qwen/Codex/Claude 交互任务前调用既有 `ensure_request_context()`。
- `tests/test_workflow.py`：新增超 96,000 字符交互请求必须在启动前拒绝的回归。
- `tasks_round/tasks_round_182_optimization_checklist.md`：登记交互式入口的预算覆盖；阶段摘要和并发限制总项仍待后续专项。
- `project_status.md`：推进至 R407。

## 验证

- `python -m unittest tests.test_workflow.WorkflowContextBudgetTests`：2/2 通过。
- `python smoke_test.py --affected workflow`：9/9 通过，工作流定向自检 78/78 通过。
- `python smoke_test.py`：8/8 通过。

## 自审

只复用既有预算规则，未改变上限、提示词内容、并发策略、模型调用或用户项目数据。
