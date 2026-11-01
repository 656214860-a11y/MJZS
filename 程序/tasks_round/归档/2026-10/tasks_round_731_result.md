# R731 结构治理轮（执行）结果：首帧生命周期 L3 发布器全量接入

来源：`架构模块接口统一.txt` 第一批第 3 项。本轮迁移首帧删除、恢复与替换的剩余 L2 直写索引路径。

## 完成内容

- L2 `keyframe_lifecycle_service.delete_keyframe()`／`restore_keyframe()`／`replace_keyframe()` 仅接收 L3 注入的发布器；移除 `save()`／`save_bytes()` 直写及替换分支的回退路径。
- L3 `stage_execution_service` 新增首帧删除、恢复、替换编排入口，以 `publish_stage_text()` 原子发布 `episode.json`，并在替换时注入 `publish_stage_bytes()` 发布 PNG。
- `desktop.py` 只调用 L3 编排入口；镜头校验、回收站语义与索引失败时的完整反向恢复不变。
- 架构门禁新增 L2 无直写且三个服务入口均需要 L3 发布器的检查。本次改测试因契约变更，断言未弱化。

## 验证

| 基线 | 结果 |
| --- | --- |
| 首帧生命周期／边界专项 | 11 条 / 0 红 |
| 受影响冒烟 | 9/9 |
| 默认冒烟 | 8/8 |
| 架构门禁 | 129/129 |
| 完整安全全量 | 3,455 条 / 0 红 / 840.9 秒 |

完整安全全量日志：`维护记录/r731_keyframe_lifecycle_safe_all.log`。

[TASK_COMPLETE]
