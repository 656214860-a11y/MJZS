# R891 UI 统一入口：确认对话框第二批

- `app.py` 的导入预览、单镜／批量删除本地视频与云端提交确认已迁移至 `ask_confirmation()`。
- 删除与付费提交使用危险确认；原同步返回与取消即拒绝的业务语义保持不变。
- 定向验证：`test_cell_menu` 40 条／0 红，`test_video_ui.AutoSubmitTests` 8 条／0 红。
- `test_video_ui` 全套在当前单次执行窗口内未收尾，未列为绿色凭据；其余业务模块的历史确认调用仍待迁移。
