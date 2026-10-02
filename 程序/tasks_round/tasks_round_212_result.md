# Round 212 结果：自动补资产心跳职责拆分

## 改动文件

- `desktop.py`
- `project_status.md`
- `tasks_round/tasks_round_212_result.md`

## 改动摘要

将 `Desktop._tick_once()` 中自动补资产的进度消息消费、续跑台账处理、后台结果收尾和下一轮轮询，收拢为私有方法 `Desktop._tick_auto_asset()`。最大重试阈值、退避规则、资产页刷新顺序和 60 秒轮询均未改变。

## 验证结果

- `py_compile desktop.py`：通过。
- 自动资产链与跨重启续跑 UI 回归：2/2 通过。
- 默认 `smoke_test.py`：8/8 通过。
