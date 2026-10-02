# Round 215 结果：云端任务监控心跳职责拆分

## 改动文件

- `desktop.py`
- `project_status.md`
- `tasks_round/tasks_round_215_result.md`

## 改动摘要

将 `Desktop._tick_once()` 中云端任务监控的结果消费和下一轮轮询，收拢为私有方法 `Desktop._tick_cloud_monitor()`。成功后的 5 秒调度、失败后的 30 秒退避及失败提示均未改变。

## 验证结果

- `py_compile desktop.py`：通过。
- 视频轮询回归：33/33 通过。
- 默认 `smoke_test.py`：8/8 通过。
