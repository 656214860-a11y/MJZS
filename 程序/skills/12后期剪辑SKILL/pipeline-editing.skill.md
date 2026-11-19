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

## 本阶段读取的项目锁

直接读取项目创作信息窗／阶段配置中由「剧本准备」填写的 `track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`splice_mode`、`style_base`、`style_directors`；`reference_mode` 仅在 Seedance 2.5 时读取并按该版本校验。赛道与来源用于继承创作上下文，规格、模型、段缝和风格用于本阶段产物及验收。
项目设置优先于外部 SKILL 的交互询问、默认推荐及独立调用示例；后续阶段直接读取，不再向用户弹问或重新收集锁。必填锁缺失或矛盾时记录缺项并退回剧本准备／项目配置补齐，不擅填默认值；选填空值仅采用当前已选 SKILL 明示且适用的默认；没有依据则保持未设置，在本阶段清单及最终交付中声明采用值和依据，不把空值当成用户已选风格卡。此规则不取消既有制作授权、预算和人工复核要求，也不关闭调试、手动执行或 SKILL 选换入口。

## 本阶段方法与交付边界

按 剪辑转场与分段检查 检查时间线与台词切点；Seedance 分段上限仅适用于对应模型，不当成所有剪辑软件的片长限制。
转场方案参考 创意转场总原则 和 转场选型速查，继承 `splice_mode` 和采用分镜的接缝事实，不能重新默认硬切或把①与②捆绑成默认方案；库内 WARN 建议不升级为硬性拒绝交付规则。

本文件直接定义本阶段职责；外部 SKILL 不能覆盖项目锁及阶段交付边界。

## 阶段核验方法

执行本阶段时，按以下职责核验：Pacing math、Cut motivation taxonomy、The hard-cut agreement checklist、The assembly spec 与 Fix in the edit, regenerate, or cover it。按采用分镜和已验证媒体安排节奏、切点与修复决策；音频预搭、音乐和声场问题才核验：sound-and-dialogue.md。

`editManifest` 必须逐段保留源视频、音轨、字幕、时间码和修复/切换依据。任一媒体不在同一时间线、切换没有可追溯依据、或预览不能审核时，不得发布 `previewMaster` 或 `editManifest`；不得借剪辑跳过上游格式核验或把重生成为未记录的替代品。

不默认加载外部包、风格库或示例库；调试、人工复核与 SKILL 选换入口保持可用。
