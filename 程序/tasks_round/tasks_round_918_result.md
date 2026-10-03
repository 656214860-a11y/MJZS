# R918 UI 统一入口：主后台忙碌态

- 中断剧本 Agent 时由 `BusyState.set_busy(False)` 统一恢复进度条、控件状态与忙碌标记，移除直接 `progress.stop()`。
- 新增架构门禁：主后台任务启动、完成、中断必须经 `BusyState` 成对管理。

验证：

- `python -m py_compile desktop.py` 通过。
- 忙碌态、按钮、通知组合架构测试：25 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

菜单、文件选择、文本层级及其它路线图覆盖率仍待审计。
