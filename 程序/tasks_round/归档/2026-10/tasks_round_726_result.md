# R726 结构治理轮（执行）结果：创意附档归档 L3 发布器接入

来源：`架构模块接口统一.txt` 第一批第 3 项。本轮迁移剧本准备流的用户文本附档归档。

## 完成内容

- L2 `idea_attachments.store()` 移除 `save_text` 直写，只接收 L3 注入的发布器；没有发布器时明确拒绝。
- L3 `stage_execution_service.archive_idea_attachments()` 注入 `publish_stage_text()`，保留非空正文校验与原有 Markdown 命名。
- `idea_chat_controller` 的后台附档准备改经 L3；新增架构门禁，防止控制器回退直调 L2 写入。

## 验证

| 基线 | 结果 |
| --- | --- |
| 附档／控制器／发布边界专项 | 8 条 / 0 红 |
| 受影响冒烟 | 9/9 |
| 默认冒烟 | 8/8 |
| 架构门禁 | 126/126 |
| 完整安全全量 | 3,446 条 / 0 红 / 759.6 秒 |

完整安全全量日志：`维护记录/r726_idea_attachment_publication_safe_all.log`。

[TASK_COMPLETE]
