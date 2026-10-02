# Round 218 结果：主后台结果心跳职责拆分

## 改动文件

- `desktop.py`

## 改动摘要

将主后台队列消费、失败后的输入控件恢复，以及自动结构剧本重派发收拢为 `_tick_async_result()`；原有队列时序不变。

## 验证结果

- `py_compile desktop.py`：通过。
- HOLLMWOOD UI 队列回归：2/2 通过。
- 默认 `smoke_test.py`：8/8 通过。
