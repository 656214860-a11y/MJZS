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

## 定向注入（00 包）

执行本阶段时，只按需读取 [editing-and-assembly.md 的 Pacing math](../00全流程SKILL/cinematic-director/references/editing-and-assembly.md#pacing-math)、[Cut motivation taxonomy](../00全流程SKILL/cinematic-director/references/editing-and-assembly.md#cut-motivation-taxonomy)、[The hard-cut agreement checklist](../00全流程SKILL/cinematic-director/references/editing-and-assembly.md#the-hard-cut-agreement-checklist)、[The assembly spec](../00全流程SKILL/cinematic-director/references/editing-and-assembly.md#the-assembly-spec) 与 [Fix in the edit, regenerate, or cover it](../00全流程SKILL/cinematic-director/references/editing-and-assembly.md#fix-in-the-edit-regenerate-or-cover-it)。按采用分镜和已验证媒体安排节奏、切点与修复决策；音频预搭、音乐和声场问题才按需读取 [sound-and-dialogue.md](../00全流程SKILL/cinematic-director/references/sound-and-dialogue.md#sound-and-dialogue)。

`editManifest` 必须逐段保留源视频、音轨、字幕、时间码和修复/切换依据。任一媒体不在同一时间线、切换没有可追溯依据、或预览不能审核时，不得发布 `previewMaster` 或 `editManifest`；不得借剪辑跳过上游格式核验或把重生成为未记录的替代品。

不得加载 00 包全文、风格库或示例库；调试、人工复核与统筹替换入口保持可用。
