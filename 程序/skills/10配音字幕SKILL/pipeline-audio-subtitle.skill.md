---
name: pipeline-audio-subtitle
displayName: 全流程·配音与字幕
description: 为已核验视频片段生成对齐音轨字幕和音频清单
stage: 配音与字幕
capabilities: [structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [audio.synthesize, subtitle.export, audio.validate]
dependsOn: [pipeline-video-generation]
conflictsWith: []
parallelizable: false
paid: true
input: [videoClips, videoManifest, adoptedStoryboard]
output: [audioTracks, subtitles, audioManifest]
constraints: [字幕与音轨对齐时间线, 导出文本符合格式契约, 不覆盖确认配音]
feedback:
  - onProgress: 更新配音字幕进度
  - onError: 报告对齐或导出失败
  - onComplete: 报告音轨字幕与清单已就绪
examples:
  - 为视频片段生成时间对齐的配音和字幕
---

## 阶段职责

承接核验过的视频片段和剧本对白，输出配音、字幕与清单；正式剪辑只使用本阶段验证通过的时间线资产。
