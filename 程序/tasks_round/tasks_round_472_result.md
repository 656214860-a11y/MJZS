# R472 结构治理轮结果

## 来源与执行条目

来源为 `tasks_round/tasks_round_461_result.md` 的 E5：统一剩余阶段上下文摘要与预算。本轮只处理 L3 工作流和 Codex 任务创建共用的预算预检边界。

## 本轮目标

在请求超过预算时，先安全合并完全重复的大段上下文，避免同一全文重复占用请求预算；唯一内容仍按原有上限拒绝，绝不擅自伪造语义摘要或启动模型。

## 改动

- `workflow_context_budget.compact_repeated_context()` 仅移除完全相同且至少 1,024 字符的重复段落，保留首份原文并在结果中标记合并数量。
- `workflow_engines` 的后台与交互入口、`codex_tasks.prepare_task()` 均接收预算服务返回的压缩后请求，确保预检结果真正传入下游。
- 增加重复大段内容可在预算预检前被合并的无 Tk 回归；唯一超限拒绝测试保持原有断言。

## 验证

- 定向：`tests.test_workflow.WorkflowContextBudgetTests`，5/5 通过。
- `python smoke_test.py --architecture`：72/72 通过。
- `python smoke_test.py`：8/8 通过。
- `python run_selftests.py --all --safe`：3,183/3,183 通过，774.2 秒，0 个文件失败。

## 约束保持

不触碰用户项目数据，不创建任务工件或启动模型进程直到预算预检成功；重复内容以首份完整原文为准，唯一内容不被截断或伪造。
