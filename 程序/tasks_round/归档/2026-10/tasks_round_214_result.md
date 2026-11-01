# Round 214 结果：自动交接包心跳职责拆分

## 改动文件

- `desktop.py`
- `project_status.md`
- `tasks_round/tasks_round_214_result.md`

## 改动摘要

将 `Desktop._tick_once()` 中自动整理交接包的后台结果收尾、失败清指纹、编辑页刷新和下一轮轮询，收拢为私有方法 `Desktop._tick_auto_handoff()`。5 分钟失败退避、60 秒轮询和原调用顺序均未改变。

## 验证结果

- `py_compile desktop.py`：通过。
- 自动交接 UI 定点回归：2/2 通过。
- 默认 `smoke_test.py`：8/8 通过。
