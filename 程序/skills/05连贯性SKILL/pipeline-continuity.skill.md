---
name: pipeline-continuity
displayName: 全流程·连贯性清单
description: 审核分镜与资产正典之间的角色场景道具和时空连续性
stage: 连贯性清单
capabilities: [structured-output, reasoning, vision]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [continuity.audit, continuity.validate]
dependsOn: [pipeline-assets]
conflictsWith: []
parallelizable: false
paid: false
input: [storyboardDraft, assetManifest, anchors]
output: [continuityLedger, repairList]
constraints: [所有冲突可定位到镜头或资产, 不擅自改写正典, 未解决冲突不得进入定稿]
feedback:
  - onProgress: 更新连贯性审计进度
  - onError: 报告阻塞性连续性冲突
  - onComplete: 报告连续性台账与修复清单已就绪
examples:
  - 审核角色服装和道具在相邻镜头中的连续性
---

## 阶段职责

将已冻结资产与分镜初稿交叉核验，建立连续性台账和可复核的冲突修复项，是分镜定稿的硬前置。

## 定向注入（00 包）

执行本阶段时，只按需读取 [continuity-bible.md 的 The continuity axes](../00全流程SKILL/cinematic-director/references/continuity-bible.md#the-continuity-axes)、[Shot-to-shot continuity schema](../00全流程SKILL/cinematic-director/references/continuity-bible.md#shot-to-shot-continuity-schema) 与 [State-change ledger](../00全流程SKILL/cinematic-director/references/continuity-bible.md#state-change-ledger)，将角色、服装、道具、地点、方向与状态变化定位到镜头和资产；读取 [failure-modes.md 的 F7 Continuity break across shots](../00全流程SKILL/cinematic-director/references/failure-modes.md#f7-continuity-break-across-shots) 与 [F19 Object permanence break](../00全流程SKILL/cinematic-director/references/failure-modes.md#f19-object-permanence-break)，以可复核根因和修复项而非静默改写处理漂移。

未解决冲突必须保留到 `repairList`，不得绕过审计进入定稿；本阶段审计连续性，但不取得 D 锁的段缝放行权。D 锁仍只由分镜定稿在资产与连续性台账都通过后执行。

不得加载 00 包全文、风格库或示例库；调试、人工裁定与统筹替换入口保持可用。
