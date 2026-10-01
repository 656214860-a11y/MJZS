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
