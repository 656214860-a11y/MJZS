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

## 本阶段读取的项目锁

直接读取项目创作信息窗／阶段配置中由「剧本准备」填写的 `track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`splice_mode`、`style_base`、`style_directors`；`reference_mode` 仅在 Seedance 2.5 时读取并按该版本校验。赛道与来源用于继承创作上下文，规格、模型、段缝和风格用于本阶段产物及验收。
项目设置优先于引用中的交互询问、默认推荐及独立调用示例；后续阶段直接读取，不再向用户弹问或重新收集锁。必填锁缺失或矛盾时记录缺项并退回剧本准备／项目配置补齐，不擅填默认值；选填空值按新版包适用默认处理，在本阶段清单及最终交付中声明采用值和依据，不把空值当成用户已选风格卡。此规则不取消既有制作授权、预算和人工复核要求，也不关闭调试、手动执行或总控替换入口。

## 新版子技能章节（按职责读取）

新版三个引擎未提供独立 PREVIS 章节，按已采用分镜的戏型选择 [通用打戏动作与节奏流程](../00全流程SKILL/AIGC创作全流程/sd-combat-engine/SKILL.md#四工作流程五步)、[真人写实动力链与空间流程](../00全流程SKILL/AIGC创作全流程/sd-real-engine/SKILL.md#四工作流程六步--asset-first-精简版) 或 [玄幻攻防与尺度流程](../00全流程SKILL/AIGC创作全流程/sd-xuanhuan-engine/SKILL.md#四工作流程五步)，仅用于校验预演动作、受力、站位、节奏和尺度，不重新设计剧情，不同时套用互斥戏型规则。非打戏不启用这些专精约束。
可播放白模仍由本阶段既有建模／运镜工具实现并验收；动作文字和提示词机检不能冒充可播放预演。外部 create-blender-story-video 不是本阶段自动默认入口，其规格或再次选锁流程不得覆盖项目设置。

本文件仅声明所需章节，不授权加载整个总控包；读取时以项目锁及本阶段职责为边界。

## 定向注入（00 包）

执行本阶段时，只按需读取 [blocking-and-staging.md 的 Blocking for AI video](../00全流程SKILL/cinematic-director/references/blocking-and-staging.md#blocking-for-ai-video) 与 [Blocking-to-prompt translation](../00全流程SKILL/cinematic-director/references/blocking-and-staging.md#blocking-to-prompt-translation)，核验首帧、镜头时间线与空间调度一致；读取 [production-workflow.md 的 Shot difficulty rubric](../00全流程SKILL/cinematic-director/references/production-workflow.md#shot-difficulty-rubric)、[Crosswalk: risk band and motion budget](../00全流程SKILL/cinematic-director/references/production-workflow.md#crosswalk-risk-band-and-motion-budget) 与 [The handoff package](../00全流程SKILL/cinematic-director/references/production-workflow.md#the-handoff-package)，在预演清单中保留风险、运动预算和可交接的验证证据。

不可播放、缺镜头时间线、调度冲突或超出已声明运动预算的预演不得进入视频生成；预演只验证，不替代正式成片或绕过人工复核。

不得加载 00 包全文、风格库或示例库；统筹可替换和调试路径保持可用。
