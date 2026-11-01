# R958 UI 统一入口：背景人物识别卡片

- 轮次类型：功能轮（UI 信息承载）。
- 背景人物识别窗的完整内容区迁移为统一 `Card`，覆盖说明、候选滚动区和批量操作区。
- 候选扫描、全选／全不选、确认写入、分镜引用清理与完成后的资产阶段跳转均保持原有逻辑。
- 卡片架构边界纳入该识别窗，后续重构不得退回裸弹窗承载完整内容区。

验证：

- `python -m unittest tests.test_assets`：81 项通过。
- `python -m unittest tests.architecture.test_card_boundary tests.architecture.test_button_boundary tests.architecture.test_dialog_boundary tests.architecture.test_notification_boundary`：43 项通过。
- `python smoke_test.py`：8 项通过、0 项失败。

已知基线：`tests.test_asset_gating` 当前因共享工作树缺少 `skip_reasons` 模块而无法导入；该测试未作为本轮通过依据，且本轮未触及其依赖链。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将路线图的卡片项标记完成。
