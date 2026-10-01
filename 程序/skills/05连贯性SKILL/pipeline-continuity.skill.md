---
name: pipeline-continuity
displayName: 全流程·连贯性清单
description: 审核分镜与资产正典之间的角色场景道具和时空连续性
stage: 连贯性清单
capabilities: [structured-output, reasoning, vision]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [continuity.audit, continuity.validate]
dependsOn: [pipeline-assets]
conflictsWith: []
parallelizable: false
paid: false
input: [storyboardDraft, assetManifest, anchors]
output: [continuityLedger, repairList]
constraints: [所有冲突可定位到镜头或资产, 不擅自改写正典, 未解决冲突不得进入定稿]
feedback:
  - onProgress: 更新连贯性审计进度
  - onError: 报告阻塞性连续性冲突
  - onComplete: 报告连续性台账与修复清单已就绪
examples:
  - 审核角色服装和道具在相邻镜头中的连续性
---

## 阶段职责

将已冻结资产与分镜初稿交叉核验，建立连续性台账和可复核的冲突修复项，是分镜定稿的硬前置。
