# Round 210 结果：自动补首帧心跳职责拆分

## 改动文件

- `desktop.py`
- `project_status.md`
- `tasks_round/tasks_round_210_result.md`

## 改动摘要

将 `Desktop._tick_once()` 中自动补首帧的进度消息消费、后台结果复核、三虎播报和下一轮轮询，收拢为私有方法 `Desktop._tick_auto_keyframe()`。调用仍位于原心跳顺序，30 秒常规轮询与失败处理均未改变。

## 验证结果

- `py_compile desktop.py`：通过。
- 自动补首帧 UI 定点回归：1/1 通过。
- 默认 `smoke_test.py`：8/8 通过。
