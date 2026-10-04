# R1015 结果：收敛白模项目上下文

## 变更

- `white_model_service.shot_directory` 只接收 `ProjectContext`；预演记录读写继续使用调用方已确定的具体目录。
- L3 统一装配白模项目上下文，白模页、预演路由、批任务和自动制作不再把裸项目根交给 L2。
- 将 `white_model_service` 从第二项待办移入 adopters，并补齐边界棘轮。

## 验证

- `python -m unittest test_previs test_previs_batch_service test_previs_monitor architecture.test_project_context_boundary architecture.test_white_model_service_json_boundary architecture.test_white_model_import_boundary`：104 passed。
- `python -m py_compile white_model_service.py white_model.py previs_routing.py previs_automation.py previs_batch_service.py stage_execution_service.py`：通过。

## 提交凭据

- 实现提交：`78184fc`。
- 凭据提交：待写入。
