# R882 UI 统一入口覆盖：通知分发器收口

## 结论

- 业务根目录中所有非确认型 `messagebox.showinfo`／`showwarning`／`showerror` 已迁入 `ui_widgets.notify()`；该入口统一复用 `NotificationDispatcher`，保留既有模态提示并在有状态栏宿主时同步状态栏。
- 通知边界门禁由“历史数量不得增加”收紧为零直调，并扩展扫描全部根目录生产模块（唯一实现边界 `ui_widgets.py` 除外）。
- 路线图仍未完成：确认对话框、忙碌状态、快捷键、提示、图标、滚动条、术语、阶段名及七项既有边界仍待逐项审计。

## 涉及范围

- 新增页面级 `notify()` 适配入口；迁移资产、云端视频、首帧、白模、分镜、SKILL、模型与工作流设置等 21 个业务模块。
- 没有改动确认型 `ask*` 对话框，避免改变删除、付费及导出等同步副作用确认语义。
- 独立启动的历史批量首帧 `.pyw` 工具不属于根目录业务模块扫描范围，保留原有自包含 UI，后续应作为独立入口审计。

## 验证

- `python -m py_compile` 覆盖本轮变更模块：通过。
- `python -m unittest tests.architecture.test_notification_boundary tests.test_ui_notifications`：9 条／0 红；通知、轮次、TODO 快照与统一棘轮门禁合计 14 条／0 红。
- 默认冒烟：8／8 通过。
- 扩展回归实际执行 230 条通过；`tests.test_cloud_video` 在直接 `python -m unittest` 调用中因测试依赖 `skip_reasons` 未落在该 import 路径而未启动，非本轮代码断言失败。
- `python run_selftests.py --all --safe` 两次均被 R881 的有效共享安全锁（PID 35544）拒绝；未绕过锁、未写入绿色全量凭据。锁释放后必须补跑完整 0 红。

## 提交

- 已提交：`4727877`（完整安全全量待 R881 锁释放后补跑）。
