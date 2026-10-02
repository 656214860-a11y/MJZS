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
output: [structuredScript, characterManifest, sceneManifest, propManifest]
constraints: [保留原始剧情事实, 提取角色场景道具, 不修改原始剧本]
feedback:
  - onProgress: 更新剧本整理进度
  - onError: 报告无法解析的剧本事实
  - onComplete: 报告结构剧本与清单已就绪
examples:
  - 将自然剧本整理为角色场景道具和分场结构
---

## 阶段职责

承接剧本准备产物，按剧本契约生成结构化正文与角色／场景／道具三类清单，作为分镜和资产的共同事实来源。情绪曲线在剧本准备阶段产出，场次拆分在初步分镜阶段产出。

## 定向注入（00 包）

执行本阶段时，只按需读取 [production-workflow.md 的 The loop 与 Gate 1 · Plan](../00全流程SKILL/cinematic-director/references/production-workflow.md#the-loop)，把自然剧本中的节拍、风格与戏剧职责整理成下游可审阅的事实；计划证据不足时退回剧本准备。
镜头功能、景别或机位等视觉语义需要进入结构稿时，只读取 [cinematic-language.md 的 Shot functions](../00全流程SKILL/cinematic-director/references/cinematic-language.md#shot-functions)，先声明镜头功能，禁止把“好看”作为唯一职责。

不得加载 00 包全文、风格库或示例库；本阶段不越权生成分镜提示词。
