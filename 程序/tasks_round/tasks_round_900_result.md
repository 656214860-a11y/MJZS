# R900 UI 统一入口：收口主壳确认

- 主壳中剧本回收、项目登记/回收、资产图片与参考图、首帧批删，以及 Codex 发送确认全部迁移至 `desktop.confirm()`。
- 删除、回收与重做操作采用危险确认；只清除失效登记也保持显式确认。恢复与发送保持普通确认；取消／关闭均不继续操作。
- UI 布局采用内容驱动高度，动作按钮保留不小于 8px 的间距与可见焦点，避免固定高度裁切确认内容。
- 验证：`py_compile desktop.py` 通过；`test_row_targets.KeyframePageTests.test_the_batch_delete_button_takes_the_highlighted_row` 1 条／0 红；`rg` 确认 `desktop.py` 无 `messagebox.ask*` 直接调用。
- 其他模块仍存在历史直接确认调用，路线图尚未完成。
