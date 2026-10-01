---
name: pipeline-script-preparation
displayName: 全流程·剧本准备
description: 锁定创作前提并产出可供结构化处理的自然剧本与创意简报
stage: 剧本准备
capabilities: [creative-writing, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [script.generate, script.validate]
dependsOn: []
conflictsWith: []
parallelizable: false
paid: false
input: [creativeBrief, modelLock, aspectRatio]
output: [scriptRaw, creativeBrief]
constraints: [确认模型与画幅前不启动, 不覆盖已确认剧本, 产物通过剧本契约]
feedback:
  - onProgress: 更新剧本准备进度
  - onError: 说明缺失前置输入或契约失败
  - onComplete: 报告自然剧本与简报已就绪
examples:
  - 根据创意简报输出可结构化的自然剧本
---

## 阶段职责

来自 `00全流程SKILL` 的创作锁与剧本门控：先确认模型、画幅和交付形态，再形成可审阅的自然剧本。
只发布确认后的简报和原稿，不替下游生成分镜、资产或媒体。
