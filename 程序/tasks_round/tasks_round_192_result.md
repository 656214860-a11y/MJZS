# Round 192 结果：后台工作流上下文预算预检

## 轮次类型

功能轮（优化清单 P1「阶段级上下文预算」的通用后台工作流子范围）。

## 完成内容

- 新增 `workflow_context_budget.ensure_request_context()`，为非交互工作流统一设置 96,000 字符请求上限。
- 通用 `workflow_engines.run_background()` 和 Qwen 直调后台入口在创建进程前执行预检。
- 超限时拒绝启动并提示缩短、拆分或先生成摘要；不改变已有剧本直连与 HOLLMWOOD 的预检行为。

## 改动文件

- `workflow_context_budget.py`
- `workflow_engines.py`
- `qwen_adapter.py`
- `tests/test_workflow.py`
- `project_status.md`
- `tasks_round/tasks_round_192_result.md`

## 验证结果

- `py_compile workflow_context_budget.py workflow_engines.py qwen_adapter.py`：通过。
- `tests.test_workflow` + `tests.test_force_quit` + `tests.test_previs`：126/126 通过。
- 默认 `smoke_test.py`：8/8 通过。

## 审查结论

通过。超限请求在引擎进程或 API 调用开始前被拒绝，且正常请求维持原有后台执行链路。
