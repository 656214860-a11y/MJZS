---
name: pipeline-storyboard-draft
displayName: 全流程·初步分镜
description: 将结构化剧本转为可审核的场次与镜头初稿
stage: 初步分镜
capabilities: [structured-output, creative-writing, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.generate, storyboard.validate]
dependsOn: [pipeline-script-structure]
conflictsWith: []
parallelizable: false
paid: false
input: [structuredScript, manifests]
output: [storyboardDraft, assetRequirements]
constraints: [镜头必须对应剧本事实, 标明场次与镜头号, 不生成最终视频提示词]
feedback:
  - onProgress: 更新初步分镜进度
  - onError: 报告缺失的场景或角色事实
  - onComplete: 报告分镜初稿已就绪
examples:
  - 根据结构剧本输出逐场镜头初稿与资产需求
---

## 阶段职责

使用已结构化的剧情事实拆场和拆镜，输出尚未采用的分镜初稿及资产需求，供资产阶段冻结正典。
