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

## 定向注入（00 包）

执行本阶段时，只按需读取 [failure-modes.md 的 60-second triage tree](../00全流程SKILL/cinematic-director/references/failure-modes.md#60-second-triage-tree)、[The cost ladder](../00全流程SKILL/cinematic-director/references/failure-modes.md#the-cost-ladder)、[Failure taxonomy F1–F19](../00全流程SKILL/cinematic-director/references/failure-modes.md#failure-taxonomy-f1f19)，以及 [editing-and-assembly.md 的 The assembly spec](../00全流程SKILL/cinematic-director/references/editing-and-assembly.md#the-assembly-spec) 和 [continuity-bible.md 的 Seed and reference registry](../00全流程SKILL/cinematic-director/references/continuity-bible.md#seed-and-reference-registry)。把观察到的症状记录为可追溯的 F 码、时间码和返工入口，并核对交付清单能追溯至剪辑、媒体、种子和参考资产。

任一质量项未通过、失败项未列入 `qualityReport`、或交付包与 `deliveryManifest` 无法回溯来源时，不得标记交付完成；返工应保留最小可执行入口，不得用“已交付”掩盖未解决的失败码。

不得加载 00 包全文、风格库或示例库；调试、人工复核与统筹替换入口保持可用。
