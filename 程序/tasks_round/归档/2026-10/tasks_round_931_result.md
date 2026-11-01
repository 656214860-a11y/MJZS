# R931 UI 统一入口：卡片首批迁移

- Qwen API 设置的整体配置区从裸 `ttk.Frame` 改为统一 `Card`，保留原有标签、输入、状态和按钮逻辑。
- 新增门禁，保证该页面持续从 `ui_widgets.Card` 创建配置承载区。

验证：

- `python tests/test_api.py`：54 条通过。
- `python -m unittest tests.architecture.test_card_boundary`：待本轮最终执行。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将该路线图项标记完成。
