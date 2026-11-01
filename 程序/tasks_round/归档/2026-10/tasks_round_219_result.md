# Round 219 结果：心跳前置维护职责拆分

## 改动文件

- `desktop.py`

## 改动摘要

将 Tk 延迟回调回收与流程进程轮询收拢为 `_tick_pre_automation()`，仍在所有自动流程前执行。

## 验证结果

- `py_compile desktop.py`：通过。
- 计时器回归：8/8 通过。
- 默认 `smoke_test.py`：8/8 通过。
