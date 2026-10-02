---
name: pipeline-video-generation
displayName: 全流程·视频生成
description: 以可播放预演和采用分镜生成可追溯的视频片段与任务清单
stage: 视频生成
capabilities: [vision, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [video.submit, video.validate]
dependsOn: [pipeline-previs]
conflictsWith: []
parallelizable: false
paid: true
input: [previsMedia, previsManifest, promptBatches, keyframes]
output: [videoClips, videoManifest]
constraints: [遵守已锁定模型与画幅, 记录任务状态, 失败片段不伪造完成]
feedback:
  - onProgress: 更新视频生成进度
  - onError: 报告任务失败和可重试状态
  - onComplete: 报告视频片段与清单已就绪
examples:
  - 根据白模预演和镜头批次提交并核验视频片段
---

## 阶段职责

执行已锁定的模型与画幅契约，生成、轮询并核验镜头片段；图生视频／参考模式以首帧为输入依据。该阶段输出是配音字幕与剪辑的共同媒体输入。

## 定向注入（00 包）

执行本阶段时，只按需读取 [ai-video-tool-adapters.md 的 The capability-first rule](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#the-capability-first-rule)、[The four prompt shapes](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#the-four-prompt-shapes)、[Per-tool adapters](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#per-tool-adapters)、[The motion budget](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#the-motion-budget) 与 [Duration strategy](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#duration-strategy)：先读取所选工具的控制面，再选择 S1／S2／S3／S4 提示词形态，继承首帧画幅并回填 `videoManifest`。

失败片段按需读取 [failure-modes.md 的 60-second triage tree](../00全流程SKILL/cinematic-director/references/failure-modes.md#60-second-triage-tree) 与 [Failure taxonomy F1–F19](../00全流程SKILL/cinematic-director/references/failure-modes.md#failure-taxonomy-f1f19)，记录可重试根因和任务状态，不能伪造完成。Seedance 2.0／2.5 的专有语法及“2.0 禁首尾帧”尚无本地权威 adapter，不能作为已验证规则写入本阶段。

不得加载 00 包全文、风格库或示例库；调试、人工复核与统筹替换入口保持可用。
