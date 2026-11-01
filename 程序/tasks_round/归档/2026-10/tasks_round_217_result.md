# Round 217 结果：自动待办裁决心跳职责拆分

## 改动文件

- `desktop.py`

## 改动摘要

将 `Desktop._tick_once()` 中自动待办与裁决调度收拢为 `_tick_auto_gates()`；20 秒节流、错误去重和状态提示不变。

## 验证结果

- `py_compile desktop.py`：通过。
- 默认 `smoke_test.py`：8/8 通过。
- `tests.test_asset_detail` 在本机两次 30 秒内未返回，未计为通过；后续需单独诊断该既有测试执行问题。
