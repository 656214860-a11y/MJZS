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
