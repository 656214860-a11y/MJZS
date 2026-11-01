# Round 220 结果：三虎事件心跳职责拆分

## 改动文件

- `desktop.py`

## 改动摘要

将主心跳末尾的三虎事件聚合收拢为 `_tick_pet_events()`；仍在所有自动流程调度之后、同一 Tk 心跳中执行。

## 验证结果

- `py_compile desktop.py`：通过。
- 宠物 Agent 回归：78/78 通过。
- 默认 `smoke_test.py`：8/8 通过。
