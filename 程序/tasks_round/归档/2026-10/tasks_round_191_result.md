# Round 191 结果：阶段模型摘要与执行器一致

## 轮次类型

功能轮（优化清单 P2「阶段配置的模型名必须与实际执行器一致」的显示链路子范围）。

## 完成内容

- `workflow_settings.summary()` 改为读取 `current()` 和 `effective_model()`，与实际派发共用
  同一模型/引擎解析链。
- 增加 DeepSeek 阶段模型回归，确保摘要显示 Qwen 兼容调用器及真正的 API 模型名，而不是保存的
  默认 Codex 配置。

## 改动文件

- `workflow_settings.py`
- `tests/test_workflow.py`
- `project_status.md`
- `tasks_round/tasks_round_191_result.md`

## 验证

- 项目内置 Python：`-m py_compile workflow_settings.py` 通过。
- `-m unittest tests.test_workflow`：76/76 通过。
- `-m unittest tests.test_skills tests.test_stage_config_hollmwood`：零退出通过。
- `smoke_test.py`：8/8 通过。

## 审查

通过：仅统一摘要的读取来源；不改模型选择规则、请求参数或执行生命周期。
