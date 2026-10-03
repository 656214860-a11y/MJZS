# R938 UI 统一入口：卡片迁移（白模预演）

- 白模预演的镜头选择窗与主预演窗内容区迁移为统一 `Card`。
- 白模导入、保存和 Blender 启动流程保持不变。
- 卡片边界测试纳入两处白模窗口。

验证：

- `python tests/test_previs.py`：53 条通过。
- `python -m unittest tests.architecture.test_card_boundary`：9 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将该路线图项标记完成。
