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

## 定向注入（00 包）

执行本阶段时，只按需读取 [image-model-adapters.md 的 Keyframe prompt anatomy](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#3-keyframe-prompt-anatomy-nine-slots-then-constraints)、[Reference-image binding, seed lock, instruction editing](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#reference-image-binding-seed-lock-instruction-editing)、[Aspect ratio and framing parameters](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#8-aspect-ratio-and-framing-parameters) 与 [Keyframe QC gate](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#9-keyframe-qc-gate)，让每张首帧继承采用镜头、资产版本与锁定画幅；再读取 [lighting-and-color.md 的 Lighting continuity for AI video](../00全流程SKILL/cinematic-director/references/lighting-and-color.md#lighting-continuity-for-ai-video)，把可复核的光源、方向与色彩锚点写入清单。

首帧或其画幅、资产版本、镜头追溯缺失时不得发布 `keyframeManifest`；不以空文件、未绑定参考或未检查光色连续性的图像充当下游通过证据。

不得加载 00 包全文、风格库或示例库；用户明确选择风格时才读取一个对应风格 reference。
