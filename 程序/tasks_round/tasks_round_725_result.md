# R725 结构治理轮（执行）结果：剧本模型成果 L3 发布器接入

来源：`架构模块接口统一.txt` 第一批第 3 项。本轮收口模型工具写入、直接 API 自动保存和 HOLLMWOOD 原稿三条剧本阶段成果路径。

## 完成内容

- L2 `writing_tools` 与 `writing_api` 移除 `save_text` 直写，写入只消费注入的发布器。
- L3 `stage_execution_service.reply_to_writing()` 注入 `publish_stage_text()`；桌面两处剧本请求只经该入口。
- 无发布器时写请求明确拒绝，不存在静默直写回退；新增 AST 门禁覆盖该边界。

## 验证

| 基线 | 结果 |
| --- | --- |
| 剧本专项 + 发布边界门禁 | 27 条 / 0 红 |
| 受影响冒烟 | 9/9 |
| 默认冒烟 | 8/8 |
| 架构门禁 | 124/124 |
| 完整安全全量 | 3,444 条 / 0 红 / 760.8 秒 |

完整安全全量日志：`维护记录/r725_writing_publication_safe_all.log`。

[TASK_COMPLETE]
