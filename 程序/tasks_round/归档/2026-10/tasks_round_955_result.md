# R955 UI 统一入口：云端工作室设置卡片

- 轮次类型：功能轮（UI 信息承载）。
- 视频页的云端工作室设置完整表单迁移为统一 `Card`，统一承载密钥目录、服务地址、模型、媒体工具与预算字段，以及联网开关和保存操作。
- 预算范围校验、`WanAdapter` 的配置校验和 `publish_cloud_video_studio_config` 发布仍使用原有逻辑；本轮不改写配置语义。
- 卡片架构边界纳入该嵌套设置方法，后续重构不得绕过统一承载组件。

验证：

- `python -m unittest tests.architecture.test_card_boundary tests.architecture.test_cloud_video_settings_boundary tests.architecture.test_input_boundary`：21 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将路线图的卡片项标记完成。
