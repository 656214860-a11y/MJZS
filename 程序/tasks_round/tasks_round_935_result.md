# R935 UI 统一入口：卡片迁移（阶段调用设置）

- 阶段调用设置窗的主表单迁移为统一 `Card`。
- 底部保存／操作区保留为独立区域，阶段配置、并行策略和保存逻辑不变。
- 卡片边界测试纳入阶段调用设置窗。

验证：

- `python -m unittest tests.architecture.test_workflow_settings_json_boundary tests.architecture.test_card_boundary`：6 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将该路线图项标记完成。
