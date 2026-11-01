# Round 208 结果：自动定稿心跳职责拆分

## 改动文件

- `desktop.py`
- `project_status.md`
- `tasks_round/tasks_round_208_result.md`

## 改动摘要

将 `Desktop._tick_once()` 中自动定稿的后台队列消费、定稿收尾同步、失败退避与下一轮轮询，收拢为私有方法 `Desktop._tick_auto_final()`。调用仍位于原心跳顺序，30 秒常规轮询与 5 分钟失败退避均未改变。

## 验证结果

- `py_compile desktop.py`：通过。
- 自动定稿 UI 定点回归：2/2 通过。
- 默认 `smoke_test.py`：8/8 通过。
