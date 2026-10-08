---
name: pipeline-previs
displayName: 全流程·白模预演
description: 以首帧和时间线验证镜头调度并发布可播放预演
stage: 白模预演
capabilities: [vision, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [previs.generate, previs.validate]
dependsOn: [pipeline-keyframe]
conflictsWith: []
parallelizable: false
paid: false
input: [keyframes, keyframeManifest, adoptedStoryboard]
output: [previsMedia, previsManifest]
constraints: [预演必须可播放, 保留镜头时间线, 不替代正式视频成片]
feedback:
  - onProgress: 更新白模预演进度
  - onError: 报告不可播放预演或调度冲突
  - onComplete: 报告白模预演已就绪
examples:
  - 用首帧和镜头时间线制作可播放白模预演
---

## 阶段职责

验证镜头运动、节奏和空间调度，只有可播放预演及其清单可进入视频生成阶段。

## 定向注入（00 包）

执行本阶段时，只按需读取 [blocking-and-staging.md 的 Blocking for AI video](../00全流程SKILL/cinematic-director/references/blocking-and-staging.md#blocking-for-ai-video) 与 [Blocking-to-prompt translation](../00全流程SKILL/cinematic-director/references/blocking-and-staging.md#blocking-to-prompt-translation)，核验首帧、镜头时间线与空间调度一致；读取 [production-workflow.md 的 Shot difficulty rubric](../00全流程SKILL/cinematic-director/references/production-workflow.md#shot-difficulty-rubric)、[Crosswalk: risk band and motion budget](../00全流程SKILL/cinematic-director/references/production-workflow.md#crosswalk-risk-band-and-motion-budget) 与 [The handoff package](../00全流程SKILL/cinematic-director/references/production-workflow.md#the-handoff-package)，在预演清单中保留风险、运动预算和可交接的验证证据。

不可播放、缺镜头时间线、调度冲突或超出已声明运动预算的预演不得进入视频生成；预演只验证，不替代正式成片或绕过人工复核。

不得加载 00 包全文、风格库或示例库；统筹可替换和调试路径保持可用。
