# R952 UI 统一入口：云端视频卡片与分层收口

- 轮次类型：功能轮（UI 信息承载与统一确认分层）。
- 云端视频 API 设置的完整表单迁移为统一 `Card`，保留可见字段标签、API Key 默认遮蔽、短暂显式查看后回藏、连接检测与保存反馈。
- 卡片边界测试纳入云端视频设置窗；隐私回归改按表单的行列语义定位，不因外层统一容器而弱化断言。
- 阶段模型的默认确认由 L4 组合根注入，L3 `stage_models` 不再反向导入 `ui_widgets`；未完成组合时按拒绝处理，绝不把无法确认误作同意。
- 更新 JSON 解析豁免与已审计注释的位置台账，仅修正源码插入后的行号偏移，未增加债务。

验证：

- `python tests/test_cloud_video.py`：12 条通过。
- `python tests/test_manual_gate.py`：16 条通过。
- `python -m unittest tests.architecture.test_layers tests.architecture.test_unification_ratchet tests.architecture.test_todo_comment_snapshot tests.architecture.test_card_boundary tests.architecture.test_cloud_video_settings_boundary`：24 条通过。
- `python smoke_test.py`：8 项通过、0 失败。
- 运行中的共享工作树含其他任务的未提交改动；R949 已禁止其写入或引用不可信的全量安全绿凭据。因此本轮不将既有全量运行误记为 R952 的凭据。

范围说明：卡片组件仍未完成全页面覆盖，本轮不将该路线图项标记完成；其余 UI 统一入口项仍须按路线图逐项审计。
