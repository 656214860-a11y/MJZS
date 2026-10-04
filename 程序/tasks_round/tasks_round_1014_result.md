# R1014 结果：收敛分镜生命周期项目上下文

## 变更

- `storyboard_lifecycle` 的工作稿判定、退役与已开工作集刷新只接收 `ProjectContext`。
- 新增 L3 包装器，定稿、桌面刷新均不再把裸项目根传给该 L2 服务。
- 将 `storyboard_lifecycle` 从第二项待办移入 adopters，并补齐边界棘轮。

## 验证

- `python -m unittest test_workflow architecture.test_project_context_boundary architecture.test_final_bundle_boundary`：107 passed。
- `python -m py_compile storyboard_lifecycle.py storyboard_final.py storyboard_final_controller.py stage_execution_service.py desktop.py`：通过。

## 提交凭据

- 实现提交：待写入。
- 凭据提交：待写入。
