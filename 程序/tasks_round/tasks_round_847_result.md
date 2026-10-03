# R847 结果｜结构治理：自动视频后台生命周期迁移

## 范围

- 自动补视频接入 `BackgroundTaskLifecycle`：提交、替换、关闭取消、成功／失败收尾均以同一 ticket 识别。
- 连续进度消息与最终结果同时携带 ticket；旧 worker 在替换或取消后不得刷新状态栏、页面或推进无人值守链。
- 补充后台任务迁移清单，明确已迁移的桌面主动入口、自动粗剪、自动交接和自动视频，以及仍待处理的资产、首帧、白模与云端监控。
- 修复仓库卫生模块接入架构门禁后的两项登记缺口：物理清理权限与可跳过测试原因常量。

## 验证

- `python -m unittest tests.test_workspace_maintenance tests.architecture.test_recycle_service tests.test_desktop_automation_service`：24 条／0 红。
- `python -m py_compile desktop.py desktop_automation_service.py`：通过。
- `run_selftests.py --all --safe`：3693 条／0 红，994.9 秒（2026-10-03）。

`[TASK_COMPLETE]`：自动视频的进度与最终交付已统一为可取消的同代次生命周期；第 6 项仍按迁移清单分批推进，未宣称整体收口。
