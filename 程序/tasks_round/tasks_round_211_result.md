# Round 211 结果：自动补白模心跳职责拆分

## 改动文件

- `desktop.py`
- `project_status.md`
- `tasks_round/tasks_round_211_result.md`

## 改动摘要

将 `Desktop._tick_once()` 中自动补白模的轮询、错误提示和工作线程消息播报，收拢为私有方法 `Desktop._tick_auto_previs()`。工作线程仍只投递消息，Tk 主线程仍在心跳中调用三虎播报；30 秒轮询间隔未改变。

## 验证结果

- `py_compile desktop.py`：通过。
- 自动白模 UI 定点回归：2/2 通过。
- 默认 `smoke_test.py`：8/8 通过。
