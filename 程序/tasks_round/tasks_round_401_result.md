# R401 功能轮结果

## 目标

收敛资产跨重启续跑台账的直接物理删除，并让回收架构门禁识别间接 `Path.unlink()` 调用。

## 改动

- `asset_resume.py`：`clear()` 改为调用受控存储服务，不再直接执行 `Path.unlink()`。
- `storage_maintenance.py`：新增 `clear_generated_workflow_state()`；仅允许删除项目 `workflows` 下指定文件名的精确、非链接内部状态文件，缺失文件保持幂等。
- `tests/architecture/test_recycle_service.py`：静态扫描改为识别任意接收者上的 `.unlink()`，违规仍输出文件与行号。
- `tests/test_storage.py`、`tests/test_asset_resume.py`：覆盖精确路径拒绝与台账服务委派。
- `tasks_round/tasks_round_182_optimization_checklist.md`：登记本次受控内部状态清理；“所有删除”总项仍未完成。
- `project_status.md`：登记验证结果并将当前待执行轮次推进至 R402。

## 验证

- `tests.test_storage` + `tests.test_asset_resume` + `tests.architecture.test_recycle_service`：17/17 通过。
- `python smoke_test.py --architecture`：31/31 通过。
- `python smoke_test.py`：8/8 通过。

## 边界

本轮不处理用户可见文件删除，也不宣称“所有删除”优化项完成；用户可见删除仍只可经 `storage_maintenance.recycle_paths()`。
