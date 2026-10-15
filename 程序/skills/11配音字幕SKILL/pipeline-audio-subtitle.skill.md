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

## 本阶段读取的项目锁

直接读取项目创作信息窗／阶段配置中由「剧本准备」填写的 `track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`splice_mode`、`style_base`、`style_directors`；`reference_mode` 仅在 Seedance 2.5 时读取并按该版本校验。赛道与来源用于继承创作上下文，规格、模型、段缝和风格用于本阶段产物及验收。
项目设置优先于引用中的交互询问、默认推荐及独立调用示例；后续阶段直接读取，不再向用户弹问或重新收集锁。必填锁缺失或矛盾时记录缺项并退回剧本准备／项目配置补齐，不擅填默认值；选填空值按新版包适用默认处理，在本阶段清单及最终交付中声明采用值和依据，不把空值当成用户已选风格卡。此规则不取消既有制作授权、预算和人工复核要求，也不关闭调试、手动执行或总控替换入口。

## 新版子技能章节（按职责读取）

声音设计读取 [声音设计流程](../00全流程SKILL/AIGC创作全流程/sd-qc-engine/SKILL.md#3-声音设计) 与 [SOUND_PLAN 模板](../00全流程SKILL/AIGC创作全流程/sd-qc-engine/references/sound-design-template.md#五sound_plan-模板)，按锁定台词和时间线记录声音层、角色音色与跨段续接，不自行改词。
只有既定人物设定要求方言时，参考 [方言使用原则](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/dialect-voice-control-dictionary.md#〇使用原则原表头) 与 [方言配音控制规则](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/dialect-voice-control-dictionary.md#一全国方言-ai-配音总控12-条--先读)，再按已定地域读取单一对应词条；不把整本方言库当作每句的提示词，也不把年轻人口吻套给不符设定的角色。

本文件仅声明所需章节，不授权加载整个总控包；读取时以项目锁及本阶段职责为边界。

## 定向注入（00 包）

执行本阶段时，只按需读取 [sound-and-dialogue.md 的 Dialogue for AI video](../00全流程SKILL/cinematic-director/references/sound-and-dialogue.md#dialogue-for-ai-video)、[Duration budgeting](../00全流程SKILL/cinematic-director/references/sound-and-dialogue.md#duration-budgeting)、[The one-speaker-per-clip rule](../00全流程SKILL/cinematic-director/references/sound-and-dialogue.md#the-one-speaker-per-clip-rule) 与 [Voice-over](../00全流程SKILL/cinematic-director/references/sound-and-dialogue.md#voice-over)：根据时间线预算每条对白，未经目标工具能力矩阵确认时按一片段一说话人处理；画外音按镜头留出的进入和退出空间安排，而不是把说明词塞满画面。

逐条核对字幕文本、入点、出点、说话人及音轨来源，并把这些事实回填 `audioManifest`。对白、音轨或字幕与 adopted storyboard 时间线不一致，或缺少可追溯来源时，不得发布 `audioManifest`；不能用静音、占位字幕或未验证的口型同步冒充通过。

不得加载 00 包全文、风格库或示例库；调试、人工复核与统筹替换入口保持可用。
