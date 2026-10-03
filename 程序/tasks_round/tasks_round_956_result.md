# R956 UI 统一入口：参考图导入卡片

- 轮次类型：功能轮（UI 信息承载）。
- 资产参考图导入窗的完整表单迁移为统一 `Card`，覆盖分类、资产、文件清单、保存目录、状态和操作区。
- 分类选择、`FileDialog` 多选、保存绑定、解除绑定确认及回收服务路径均保持原有逻辑。
- 卡片架构边界纳入该导入窗，后续重构不得退回裸 `ttk.Frame` 承载完整表单。

验证：

- `python -m unittest tests.test_reference_images tests.architecture.test_card_boundary tests.architecture.test_button_boundary tests.architecture.test_file_dialog_boundary tests.architecture.test_notification_boundary`：62 条通过。
- `python smoke_test.py`：8 项通过、0 项失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将路线图的卡片项标记完成。
