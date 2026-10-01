---
name: pipeline-editing
displayName: 全流程·后期剪辑
description: 汇集视频音频字幕并发布可审核的预览与成片清单
stage: 后期剪辑
capabilities: [structured-output, reasoning, vision]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [edit.assemble, edit.validate]
dependsOn: [pipeline-video-generation, pipeline-audio-subtitle]
conflictsWith: []
parallelizable: false
paid: false
input: [videoClips, videoManifest, audioTracks, subtitles, audioManifest]
output: [previewMaster, editManifest]
constraints: [视频音频字幕使用同一时间线, 保留源片段映射, 不跳过格式核验]
feedback:
  - onProgress: 更新后期剪辑进度
  - onError: 报告媒体缺失或时间线冲突
  - onComplete: 报告预览成片与剪辑清单已就绪
examples:
  - 将核验视频音轨字幕组装为可审核预览成片
---

## 阶段职责

在视频和音频字幕都已通过验证后组装时间线，输出预览或成片及可追溯剪辑清单，交给最终质检。
