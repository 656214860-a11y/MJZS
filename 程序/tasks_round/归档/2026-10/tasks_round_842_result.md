# R842 结果：后台任务生命周期首批

- 本轮为结构治理轮：收口路线图第二批第 6 项的桌面主动任务入口。`Desktop.async_()` 以 `BackgroundTaskLifecycle` 统一提交、逻辑取消、成功／失败收尾；取消或新代次替换后，迟到线程结果被拒绝，不会再调用 UI 回调。
- 不强杀任意 Python 线程，避免把线程终止伪装成安全能力；预演、媒体及自动阶段的专用进程继续维持既有可终止协议，后续按此契约逐批迁移。
- `project_status.md` 的欠账减少：后台任务生命周期已从“无统一主动任务入口”变为桌面主入口试点完成，第 6 项尚未整体收口。

## 验证

- `run_selftests.py -k 'desktop_automation_service desktop_close' --safe`：5 条／0 红。
- `python smoke_test.py`：8/8 通过；`python smoke_test.py --architecture`：226/226 通过。
- R842−R841=1，且第 6 项仍在分批迁移，未触发完整安全全量；`last_full_safe_all_round` 保持 R841。
