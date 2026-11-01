# R953 UI 统一入口：本地视频设置卡片

- 轮次类型：功能轮（UI 信息承载）。
- 本地 ComfyUI 视频设置的完整表单迁移为统一 `Card`，统一承载地址、工作流、节点字段、说明和操作区。
- 工作流文件选择仍由 `FileDialog` 处理；节点检测、模型预检和保存仍经原有 `LocalAPI`、`prepare_graph` 及 L3 发布路径，不改变业务语义。
- 卡片架构边界新增本地视频设置窗，后续重构不得绕过统一承载组件。

验证：

- `python -m unittest tests.test_local_video_settings_service tests.architecture.test_local_video_settings_boundary tests.architecture.test_card_boundary`：17 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将路线图的卡片项标记完成。
