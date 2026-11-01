# Round 197 结果：分镜旧接口 facade 收敛

## 轮次类型

功能轮（优化清单 P1「旧接口兼容集中到 facade 模块」的分镜领域子范围）。

## 完成内容

- 分镜计划、定稿、回收和工作流任务直接使用目录服务。
- 需要选择状态的分镜计划改为直接使用选择服务。
- `storyboard_catalog` 不再作为领域业务模块的中转依赖，继续保留给旧调用方兼容。

## 改动文件

- `storyboard_plan_service.py`
- `storyboard_final.py`
- `storyboard_recycle_service.py`
- `workflow_tasks.py`
- `project_status.md`
- `tasks_round/tasks_round_197_result.md`

## 验证结果

- 受影响模块 `py_compile`：通过。
- 静态循环门禁 + 分镜计划、定稿、回收、工作流回归：101/101 通过。
- 默认 `smoke_test.py`：8/8 通过。

## 审查结论

通过。业务逻辑依赖无界面领域服务，兼容 facade 的职责边界更清晰。
