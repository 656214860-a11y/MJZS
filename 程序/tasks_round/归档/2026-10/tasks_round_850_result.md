# R850 结果｜结构治理：云端监控生命周期迁移

## 范围

- 跨页面云端任务轮询接入 `BackgroundTaskLifecycle`；每次提交以 ticket 绑定结果。
- 关闭窗口或发起新代次后，迟到的监控成功／失败结果均不得写状态栏、清除忙碌状态或改变下一次节流。

## 验证

- `python -m py_compile desktop.py desktop_automation_service.py`：通过。
- `run_selftests.py --safe -k ui_edges desktop_automation_service`：122 条／0 红，187.6 秒。
- `run_selftests.py --all --safe`：3696 条／0 红，1021.0 秒。
- `smoke_test.py`：8／8 通过。

`[TASK_COMPLETE]`：云端跨页监控完成迟到结果隔离；白模专用进程仍按路线图继续治理。
