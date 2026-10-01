---
name: pipeline-script-structure
displayName: 全流程·剧本整理
description: 将已确认自然剧本整理为下游可消费的结构化剧本与要素清单
stage: 剧本结构
capabilities: [structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [script.generate, script.validate]
dependsOn: [pipeline-script-preparation]
conflictsWith: []
parallelizable: false
paid: false
input: [scriptRaw, creativeBrief]
output: [structuredScript, manifests]
constraints: [保留原始剧情事实, 提取角色场景道具, 不修改原始剧本]
feedback:
  - onProgress: 更新剧本整理进度
  - onError: 报告无法解析的剧本事实
  - onComplete: 报告结构剧本与清单已就绪
examples:
  - 将自然剧本整理为角色场景道具和分场结构
---

## 阶段职责

承接剧本准备产物，按剧本契约生成结构化正文及五类清单，作为分镜和资产的共同事实来源。
