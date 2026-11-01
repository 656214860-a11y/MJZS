# R901 UI 统一入口：清理生产确认直连

- `skill_panel.py` 的 SKILL 回收、恢复默认值和付费执行；`storyboard_files.py` 的保存、回收、恢复和重排镜头编号均改用统一确认入口。
- 三虎一键执行的默认确认也迁移至统一窗口；没有可用界面或弹窗失败时按未确认处理，避免未经确认启动自动制作。测试注入的 `asker` 语义不变。
- 验证：`py_compile pet_ui.py skill_panel.py storyboard_files.py` 通过；分镜定稿回归 13 条／0 红、阶段配置定向回归 4 条／0 红、镜头编号回归 1 条／0 红；生产 Python 搜索无 `messagebox.ask*` 调用（`ui_widgets.py` 仅保留迁移说明文字）。
- 路线图的按钮、文字层级、卡片和逐项覆盖审计尚未全部完成。
