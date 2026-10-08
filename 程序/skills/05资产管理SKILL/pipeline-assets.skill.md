---
name: pipeline-assets
displayName: 全流程·资产管理
description: 基于分镜初稿建立角色场景道具正典与可追溯资产清单
stage: 资产管理
capabilities: [vision, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [asset.plan, asset.validate]
dependsOn: [pipeline-animatic]
conflictsWith: []
parallelizable: false
paid: false
input: [storyboardDraft, assetRequirements, characterManifest, sceneManifest, propManifest, sceneBreakdown, emotionCurve]
output: [assetManifest, canonBoard, anchors]
constraints: [资产由剧本与分镜事实导出, 记录版本与来源, 不覆盖已确认资产]
feedback:
  - onProgress: 更新资产管理进度
  - onError: 报告资产需求与正典冲突
  - onComplete: 报告资产清单与锚点已就绪
examples:
  - 从分镜需求建立角色场景道具的正典资产清单
---

## 阶段职责

执行全流程资料中的 Asset-First 资产锁定：把初步分镜的实体需求变为可追溯资产、正典板和连续性锚点。

## 定向注入（00 包）

执行本阶段时，只按需读取 [continuity-bible.md 的 Identity string contract](../00全流程SKILL/cinematic-director/references/continuity-bible.md#the-identity-string-contract)、[Character schema](../00全流程SKILL/cinematic-director/references/continuity-bible.md#character-schema) 与 [Asset naming convention](../00全流程SKILL/cinematic-director/references/continuity-bible.md#asset-naming-convention)，把剧本和分镜事实固化为有来源、版本和稳定身份串的资产正典；读取 [image-model-adapters.md 的 Character consistency playbook](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#4-character-consistency-playbook-cheapest-first)，根据已选工具的控制面决定参考图、种子或编辑约束。

资产缺少可追溯来源、身份锚点或版本时不得进入正典；发现冲突只生成待修复项，不覆盖已确认资产。4 View／16 项锁及 T1→T3 亲缘推导的指定权威源尚不可用，不能把它们伪装为本阶段已验证规则。

不得加载 00 包全文、风格库或示例库；只有用户明确选择风格时才按需读取对应的单一风格 reference。
