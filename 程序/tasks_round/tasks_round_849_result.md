# R849 结果｜结构治理：自动首帧后台生命周期迁移

## 范围

- 自动补首帧接入 `BackgroundTaskLifecycle`；共享的一键执行与无人值守派发均绑定同一 ticket。
- 连续日志和最终结果按 ticket 验证；替换、禁用或关窗后的旧 worker 不得刷新 UI 或推进阶段。
- 保持既有首帧缺口、参考资产检查与重试语义。

## 验证

- `python -m py_compile desktop.py desktop_automation_service.py`：通过。
- `run_selftests.py --safe -k ui_edges pet_ui desktop_automation_service`：681 条／0 红，296.0 秒。
- `smoke_test.py`：8／8 通过。

`[TASK_COMPLETE]`：自动首帧完成进度／结果同代次交付迁移；后续继续白模与云端监控。
