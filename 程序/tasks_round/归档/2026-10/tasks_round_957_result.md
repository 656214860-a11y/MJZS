# R957 UI 统一入口：云图片模型设置卡片

- 轮次类型：功能轮（UI 信息承载）。
- 云图片模型设置表单迁移为统一 `Card`，覆盖密钥说明、密钥输入、状态反馈和操作区。
- 密钥脱敏、统一 `.env` 保存、保存失败反馈及外部 Comfy 账户／API Key 页面入口均保持原有逻辑。
- 卡片架构边界纳入该设置窗，后续重构不得退回裸 `ttk.Frame` 承载完整表单。

验证：

- `python -m unittest tests.test_api tests.architecture.test_card_boundary tests.architecture.test_button_boundary tests.architecture.test_dialog_boundary tests.architecture.test_notification_boundary`：96 项通过。
- `python smoke_test.py`：8 项通过、0 项失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将路线图的卡片项标记完成。
