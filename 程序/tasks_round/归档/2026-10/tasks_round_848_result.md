# R848 结果｜结构治理：自动资产后台生命周期迁移

## 范围

- 自动补资产接入 `BackgroundTaskLifecycle`；派发、关闭取消与最终收尾以同一 ticket 识别。
- 进度和最终结果均携带 ticket；替换或取消后的旧 worker 不得刷新状态栏、页面、资产续跑台账或推进无人值守链。
- 保留既有缺图重试、退避与台账规则；仅统一后台交付边界。

## 验证

- `python -m py_compile desktop.py desktop_automation_service.py`：通过。
- `run_selftests.py --safe -k ui_edges desktop_automation_service`：120 条／0 红，169.9 秒。
- `smoke_test.py`：8／8 通过。

`[TASK_COMPLETE]`：自动资产已完成进度／结果同代次交付迁移；第 6 项仍按清单继续首帧、白模与云端监控。
