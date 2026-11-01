# R937 UI 统一入口：卡片迁移（三虎模型窗）

- 三虎模型设置与模型管理共用的建窗内容区迁移为统一 `Card`。
- 模型表格、连接检测、供应商配置和密钥操作逻辑保持不变。
- 卡片边界测试纳入共享建窗函数。

验证：

- `python tests/test_pet_settings.py`：7 条通过。
- `python -m unittest tests.architecture.test_card_boundary`：7 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将该路线图项标记完成。
