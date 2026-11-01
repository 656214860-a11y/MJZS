# R890 UI 统一入口：确认对话框（进行中）

- 新增 `ui_widgets.ask_confirmation()`：以 `ConfirmDialog` 提供旧式同步布尔结果；关闭、Esc 或父窗销毁均视为拒绝。
- `project_settings.confirm_unattended()` 与 `seedream_settings.confirm_unsettled()` 已经迁移；两者涉及自动执行或可能重复扣费，按危险确认呈现。
- 定向验证：`test_seedream_direct`、`test_ui_widgets_dialogs` 合计 19 条／0 红。
- 尚有历史 `messagebox.ask*` 调用待替换；本报告不代表路线图完成。
