---
name: pipeline-delivery
displayName: 全流程·质检与交付
description: 核验成片字幕和清单并输出交付报告与可恢复交付包
stage: 质检与交付
capabilities: [structured-output, reasoning, vision]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [delivery.validate, delivery.package]
dependsOn: [pipeline-editing]
conflictsWith: []
parallelizable: false
paid: false
input: [previewMaster, editManifest, subtitles, audioManifest]
output: [qualityReport, deliveryPackage, deliveryManifest]
constraints: [质检报告列出失败项, 交付包可追溯来源, 未通过质检不得标记交付完成]
feedback:
  - onProgress: 更新质检交付进度
  - onError: 报告质量阻塞与返工入口
  - onComplete: 报告交付包和验收结果
examples:
  - 对成片字幕与清单执行质检并生成交付包
---

## 阶段职责

执行全流程的最终质量门禁，输出可审计质检报告、交付包和交付清单；失败项保留为可追踪返工依据。

## 本阶段读取的项目锁

直接读取项目创作信息窗／阶段配置中由「剧本准备」填写的 `track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`splice_mode`、`style_base`、`style_directors`；`reference_mode` 仅在 Seedance 2.5 时读取并按该版本校验。赛道与来源用于继承创作上下文，规格、模型、段缝和风格用于本阶段产物及验收。
项目设置优先于引用中的交互询问、默认推荐及独立调用示例；后续阶段直接读取，不再向用户弹问或重新收集锁。必填锁缺失或矛盾时记录缺项并退回剧本准备／项目配置补齐，不擅填默认值；选填空值按新版包适用默认处理，在本阶段清单及最终交付中声明采用值和依据，不把空值当成用户已选风格卡。此规则不取消既有制作授权、预算和人工复核要求，也不关闭调试、手动执行或总控替换入口。

## 新版子技能章节（按职责读取）

按 [连续性核对](../00全流程SKILL/AIGC创作全流程/sd-qc-engine/SKILL.md#1-连续性检查跨镜跨集)、[转场检查](../00全流程SKILL/AIGC创作全流程/sd-qc-engine/SKILL.md#2-剪辑转场与分段检查)、[声音检查](../00全流程SKILL/AIGC创作全流程/sd-qc-engine/SKILL.md#3-声音设计) 组织成片复核，按 [出稿机检](../00全流程SKILL/AIGC创作全流程/sd-qc-engine/SKILL.md#4-出稿机检) 和 [统一裁决](../00全流程SKILL/AIGC创作全流程/sd-qc-engine/references/rule-taxonomy-and-verdict.md#四pass--warn--fail-三态定义跨阶段统一) 分别记录硬性失败与建议项。
该引擎的出稿机检只证明稿件层检查结果，不能替代本阶段真实成片、音轨、字幕与交付文件验收。M0/M1 文本交付按声明形态核对，不索要不存在的图片；交付形态若要求实际成片，则必须有真实可播放媒体，不能用稿件或占位清单放行。

本文件仅声明所需章节，不授权加载整个总控包；读取时以项目锁及本阶段职责为边界。

## 定向注入（00 包）

执行本阶段时，只按需读取 [failure-modes.md 的 60-second triage tree](../00全流程SKILL/cinematic-director/references/failure-modes.md#60-second-triage-tree)、[The cost ladder](../00全流程SKILL/cinematic-director/references/failure-modes.md#the-cost-ladder)、[Failure taxonomy F1–F19](../00全流程SKILL/cinematic-director/references/failure-modes.md#failure-taxonomy-f1f19)，以及 [editing-and-assembly.md 的 The assembly spec](../00全流程SKILL/cinematic-director/references/editing-and-assembly.md#the-assembly-spec) 和 [continuity-bible.md 的 Seed and reference registry](../00全流程SKILL/cinematic-director/references/continuity-bible.md#seed-and-reference-registry)。把观察到的症状记录为可追溯的 F 码、时间码和返工入口，并核对交付清单能追溯至剪辑、媒体、种子和参考资产。

任一质量项未通过、失败项未列入 `qualityReport`、或交付包与 `deliveryManifest` 无法回溯来源时，不得标记交付完成；返工应保留最小可执行入口，不得用“已交付”掩盖未解决的失败码。

不得加载 00 包全文、风格库或示例库；调试、人工复核与统筹替换入口保持可用。
