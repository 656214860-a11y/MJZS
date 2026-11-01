# 第 399 轮结果

## 完成内容

- 新增 `tests/architecture/test_import_error_boundaries.py`，把根目录生产模块的 `ImportError` 许可点固定为四种明确职责。
- 历史旧接口只经 `legacy_compat` 处理，且仍声明 2027-03-31 淘汰日期；平台、解释器和成果核验的容错保留其各自失败语义。
- 将优化清单“旧接口兼容集中到 facade”标记为已完成。

## 改动文件

- `tests/architecture/test_import_error_boundaries.py`
- `tasks_round/tasks_round_182_optimization_checklist.md`
- `project_status.md`
- `tasks_round/tasks_round_399_result.md`

## 验证

- `smoke_test.py --architecture`：31/31 通过。
- `run_selftests.py --safe --serial -k legacy_compat stage_completion_service platform_tools hash_backend`：26/26 通过。
- `smoke_test.py`：8/8 通过。
