# R936 UI 统一入口：卡片迁移（设置枢纽）

- 齿轮入口打开的多标签设置枢纽，其主内容区迁移为统一 `Card`。
- 内部标签页、选项切换与操作逻辑保持不变。
- 卡片边界测试纳入设置枢纽。

验证：

- `python tests/test_pet_settings.py`：6 条通过。
- `python -m unittest tests.architecture.test_card_boundary`：6 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将该路线图项标记完成。
