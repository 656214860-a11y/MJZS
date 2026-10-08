---
name: pipeline-audio-subtitle
displayName: 全流程·配音与字幕
description: 为定稿分镜的对白与时间线事实生成对齐音轨字幕和音频清单
stage: 配音与字幕
capabilities: [structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [audio.synthesize, subtitle.export, audio.validate]
dependsOn: [pipeline-storyboard-final]
conflictsWith: []
parallelizable: false
paid: true
input: [adoptedStoryboard, dialogueFacts]
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

承接定稿分镜的对白与时间线事实，输出配音、字幕与清单；正式剪辑只使用本阶段验证通过的时间线资产。

## 定向注入（00 包）

执行本阶段时，只按需读取 [sound-and-dialogue.md 的 Dialogue for AI video](../00全流程SKILL/cinematic-director/references/sound-and-dialogue.md#dialogue-for-ai-video)、[Duration budgeting](../00全流程SKILL/cinematic-director/references/sound-and-dialogue.md#duration-budgeting)、[The one-speaker-per-clip rule](../00全流程SKILL/cinematic-director/references/sound-and-dialogue.md#the-one-speaker-per-clip-rule) 与 [Voice-over](../00全流程SKILL/cinematic-director/references/sound-and-dialogue.md#voice-over)：根据时间线预算每条对白，未经目标工具能力矩阵确认时按一片段一说话人处理；画外音按镜头留出的进入和退出空间安排，而不是把说明词塞满画面。

逐条核对字幕文本、入点、出点、说话人及音轨来源，并把这些事实回填 `audioManifest`。对白、音轨或字幕与 adopted storyboard 时间线不一致，或缺少可追溯来源时，不得发布 `audioManifest`；不能用静音、占位字幕或未验证的口型同步冒充通过。

不得加载 00 包全文、风格库或示例库；调试、人工复核与统筹替换入口保持可用。
