---
name: pipeline-keyframe
displayName: 全流程·首帧管理
description: 为采用分镜建立非空且可追溯的首帧与关键帧清单
stage: 首帧管理
capabilities: [vision, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [keyframe.generate, keyframe.validate]
dependsOn: [pipeline-storyboard-final]
conflictsWith: []
parallelizable: false
paid: false
input: [adoptedStoryboard, promptBatches, assetManifest]
output: [keyframes, keyframeManifest]
constraints: [每个首帧文件非空, 绑定镜头和资产版本, 失败不发布半成品]
feedback:
  - onProgress: 更新首帧管理进度
  - onError: 报告缺帧或质量不合格镜头
  - onComplete: 报告首帧清单已就绪
examples:
  - 为采用镜头生成并核验可追溯的首帧
---

## 阶段职责

以采用分镜和资产正典为唯一输入，完成首帧生成、导入和质量核验，不能用空文件作为下游通过证据。
