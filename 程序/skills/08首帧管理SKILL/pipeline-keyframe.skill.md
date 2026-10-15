---
name: pipeline-keyframe
displayName: 全流程·首帧管理
description: 为采用分镜建立非空且可追溯的首帧与关键帧清单
stage: 首帧管理
capabilities: [vision, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [keyframe.generate, keyframe.validate]
dependsOn: [pipeline-storyboard-final]
conflictsWith: []
parallelizable: false
paid: false
input: [adoptedStoryboard, promptBatches, assetManifest]
output: [keyframes, keyframeManifest]
constraints: [每个首帧文件非空, 绑定镜头和资产版本, 失败不发布半成品]
feedback:
  - onProgress: 更新首帧管理进度
  - onError: 报告缺帧或质量不合格镜头
  - onComplete: 报告首帧清单已就绪
examples:
  - 为采用镜头生成并核验可追溯的首帧
---

## 阶段职责

以采用分镜和资产正典为唯一输入，完成首帧生成、导入和质量核验，不能用空文件作为下游通过证据。

## 本阶段读取的项目锁

直接读取项目创作信息窗／阶段配置中由「剧本准备」填写的 `track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`splice_mode`、`style_base`、`style_directors`；`reference_mode` 仅在 Seedance 2.5 时读取并按该版本校验。赛道与来源用于继承创作上下文，规格、模型、段缝和风格用于本阶段产物及验收。
项目设置优先于引用中的交互询问、默认推荐及独立调用示例；后续阶段直接读取，不再向用户弹问或重新收集锁。必填锁缺失或矛盾时记录缺项并退回剧本准备／项目配置补齐，不擅填默认值；选填空值按新版包适用默认处理，在本阶段清单及最终交付中声明采用值和依据，不把空值当成用户已选风格卡。此规则不取消既有制作授权、预算和人工复核要求，也不关闭调试、手动执行或总控替换入口。

## 新版子技能章节（按职责读取）

按 [故事板图与面板链](../00全流程SKILL/AIGC创作全流程/sd-storyboard-engine/SKILL.md#七故事板图面板链) 核对故事板与首帧的用途，故事板不等同于单镜首帧，标注版不进入投喂。
继承 [素材形态判定](../00全流程SKILL/AIGC创作全流程/sd-asset-engine/SKILL.md#step-38-素材形态判定决定-step-4-的产出物)、[按形态分流与 M2 路径](../00全流程SKILL/AIGC创作全流程/sd-asset-engine/SKILL.md#step-4-按模板生成按形态分流) 和 [出图授权边界](../00全流程SKILL/AIGC创作全流程/sd-asset-engine/SKILL.md#step-45-出图授权出图口令禁止默认)。默认只整理提示词与清单；M0/M1 不冒充已有图片，不因缺图阻断纯文本交付。已入库 M2 图片可直接登记、复用与质检；实际出图须有明确出图授权，调用本阶段不等于自动获得出图授权。只有实际生成／导入且通过验收的首帧才写入可用 keyframeManifest；待生成项保留待办，不能伪装为完成。

本文件仅声明所需章节，不授权加载整个总控包；读取时以项目锁及本阶段职责为边界。

## 定向注入（00 包）

执行本阶段时，只按需读取 [image-model-adapters.md 的 Keyframe prompt anatomy](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#3-keyframe-prompt-anatomy-nine-slots-then-constraints)、[Reference-image binding, seed lock, instruction editing](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#reference-image-binding-seed-lock-instruction-editing)、[Aspect ratio and framing parameters](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#8-aspect-ratio-and-framing-parameters) 与 [Keyframe QC gate](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#9-keyframe-qc-gate)，让每张首帧继承采用镜头、资产版本与锁定画幅；再读取 [lighting-and-color.md 的 Lighting continuity for AI video](../00全流程SKILL/cinematic-director/references/lighting-and-color.md#lighting-continuity-for-ai-video)，把可复核的光源、方向与色彩锚点写入清单。

首帧或其画幅、资产版本、镜头追溯缺失时不得发布 `keyframeManifest`；不以空文件、未绑定参考或未检查光色连续性的图像充当下游通过证据。

不得加载 00 包全文、风格库或示例库；用户明确选择风格时才读取一个对应风格 reference。
