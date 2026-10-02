---
name: pipeline-assets
displayName: 全流程·资产管理
description: 基于分镜初稿建立角色场景道具正典与可追溯资产清单
stage: 资产管理
capabilities: [vision, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [asset.plan, asset.validate]
dependsOn: [pipeline-storyboard-draft]
conflictsWith: []
parallelizable: false
paid: false
input: [storyboardDraft, assetRequirements, characterManifest, sceneManifest, propManifest, sceneBreakdown, emotionCurve]
output: [assetManifest, canonBoard, anchors]
constraints: [资产由剧本与分镜事实导出, 记录版本与来源, 不覆盖已确认资产]
feedback:
  - onProgress: 更新资产管理进度
  - onError: 报告资产需求与正典冲突
  - onComplete: 报告资产清单与锚点已就绪
examples:
  - 从分镜需求建立角色场景道具的正典资产清单
---

## 阶段职责

执行全流程资料中的 Asset-First 资产锁定：把初步分镜的实体需求变为可追溯资产、正典板和连续性锚点。
