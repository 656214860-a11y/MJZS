# R934 UI 统一入口：卡片迁移（提示词优化器）

- 提示词优化器设置窗的整张配置表单迁移为统一 `Card`，字段、状态反馈、保存与删除确认逻辑不变。
- UI 回归测试改为按表单的行列语义查找控件，允许统一容器存在，仍校验服务商、地址、模型和密钥的交互。
- 卡片边界测试纳入提示词优化器设置窗。

验证：

- `python tests/test_mcp_settings.py`：8 条通过。
- `python -m unittest tests.architecture.test_card_boundary`：4 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将该路线图项标记完成。
