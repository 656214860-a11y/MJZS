---
name: pipeline-storyboard-final
displayName: 全流程·分镜定稿
description: 根据连续性台账将审核通过的分镜初稿收敛为采用分镜和提示词批次
stage: 分镜定稿
capabilities: [structured-output, creative-writing, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.finalize, storyboard.validate]
dependsOn: [pipeline-continuity]
conflictsWith: []
parallelizable: false
paid: false
input: [storyboardDraft, continuityLedger, assetManifest]
output: [adoptedStoryboard, promptBatches]
constraints: [只采用连续性审核通过的镜头, 保留镜头与资产追溯关系, 生成批次标识]
feedback:
  - onProgress: 更新分镜定稿进度
  - onError: 报告未解决的连续性阻塞
  - onComplete: 报告采用分镜与批次已就绪
examples:
  - 将连续性通过的分镜初稿定稿并生成镜头批次
---

## 阶段职责

只以通过审计的资产和连续性台账为依据，发布采用分镜、镜头提示词与批次关系，供首帧制作使用。
