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
