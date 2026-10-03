# R932 UI 统一入口：卡片迁移（TTS 设置）

- TTS API 设置窗的配置承载区迁移为统一 `Card`，保留现有可见标签、状态反馈与操作按钮。
- 卡片边界测试扩展到 Qwen、TTS 两个已迁移 API 设置窗。

验证：

- `python tests/test_tts.py`：40 条通过。
- `python -m unittest tests.architecture.test_card_boundary`：2 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将该路线图项标记完成。
