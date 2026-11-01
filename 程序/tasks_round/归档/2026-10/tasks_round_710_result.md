# R710 结构治理轮（执行）结果：自动粗剪完成标记发布器注入

来源：`架构模块接口统一.txt` 第一批第 3 项。本轮只迁移自动粗剪完成标记这一 L2 写服务；未改变业务字段、落盘路径、UI 交互或用户项目数据。

## 完成内容

- `edit_service.save_automatic_assemble_marker()` 改为只接收已定位的目标路径和调用方注入的发布器，不再自行定位 edit 阶段或调用 `agent.core.save()`。
- `stage_execution_service.save_automatic_assemble_marker()` 成为唯一 L3 编排入口：定位 edit 阶段、注入 `publish_stage_text()`，并维持原有 JSON 标记内容及原子发布边界。
- `desktop` 自动粗剪流程只调用 L3 编排入口；架构测试固化 UI→L3→L2 的发布器依赖方向。

## 验证

| 基线 | 结果 |
| --- | --- |
| 定向单元（剪辑服务 + 发布边界） | 7 条 / 0 红 |
| 受影响冒烟 | 9/9 |
| 默认冒烟 | 8/8 |
| 架构门禁 | 108/108 |
| 完整安全全量 | 3,417 条 / 0 红 / 763.8 秒 |

完整安全全量日志：`维护记录/r710_edit_marker_safe_all.log`。

## 后续

L2 写服务的发布器注入仍按服务逐批推进；本轮不宣告其他标记或打包写服务已经迁移。

`[TASK_COMPLETE]`
