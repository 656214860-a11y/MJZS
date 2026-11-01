# Round 213 结果：自动补视频心跳职责拆分

## 改动文件

- `desktop.py`
- `project_status.md`
- `tasks_round/tasks_round_213_result.md`

## 改动摘要

将 `Desktop._tick_once()` 中自动补视频的进度消息消费、结果去重、后台结果收尾和下一轮轮询，收拢为私有方法 `Desktop._tick_auto_video()`。状态栏去重、5 分钟失败退避和 60 秒轮询均未改变。

## 验证结果

- `py_compile desktop.py`：通过。
- 自动视频 UI 定点回归：1/1 通过。
- 默认 `smoke_test.py`：8/8 通过。
