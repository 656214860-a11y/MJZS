# R851 结果｜结构治理：白模预演专用进程生命周期

## 范围

- 自动白模批次以 `BackgroundTaskLifecycle` 的 ticket 绑定最终播报；替换或取消后的旧线程即使迟到退出，也不能再向桌宠或主界面交付完成／失败消息。
- 关闭、禁用自动白模时同步逻辑取消 ticket；外部 Blender／引擎进程仍只由项目登记表精确终止。

## 验证

- `run_selftests.py --safe -k desktop_automation_service previs`：99 条／0 红，11.3 秒。
- `smoke_test.py`：8／8 通过。

`[TASK_COMPLETE]`：白模专用进程已纳入后台代次交付约束；完整安全全量按三轮门禁在后续轮次重新执行。
