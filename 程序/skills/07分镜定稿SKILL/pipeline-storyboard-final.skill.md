---
name: pipeline-storyboard-final
displayName: 全流程·分镜定稿
description: 根据连续性台账将审核通过的分镜初稿收敛为采用分镜和提示词批次
stage: 分镜定稿
capabilities: [structured-output, creative-writing, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.finalize, storyboard.validate]
dependsOn: [pipeline-continuity]
conflictsWith: []
parallelizable: false
paid: false
input: [storyboardDraft, continuityLedger, assetManifest]
output: [adoptedStoryboard, promptBatches]
constraints: [只采用连续性审核通过的镜头, 保留镜头与资产追溯关系, 生成批次标识]
feedback:
  - onProgress: 更新分镜定稿进度
  - onError: 报告未解决的连续性阻塞
  - onComplete: 报告采用分镜与批次已就绪
examples:
  - 将连续性通过的分镜初稿定稿并生成镜头批次
---

## 阶段职责

只以通过审计的资产和连续性台账为依据，发布采用分镜、镜头提示词与批次关系，供首帧制作使用。

## 定向注入（00 包）

执行本阶段时，只按需读取 [cinematic-language.md 的 Shot functions](../00全流程SKILL/cinematic-director/references/cinematic-language.md#shot-functions)，先按目标模型的能力选择可执行的镜头职责与表达形态；读取 [prompt-lexicon.md 的 The conversion procedure](../00全流程SKILL/cinematic-director/references/prompt-lexicon.md#the-conversion-procedure) 与 [The one-dominant-move rule](../00全流程SKILL/cinematic-director/references/prompt-lexicon.md#the-one-dominant-move-rule)，把已采用的镜头事实渲染为明确、可追溯的提示词批次，而不是凭“好看”补写语义。

D 锁只在本阶段放行：按需读取 [continuity-bible.md 的 Shot-to-shot continuity schema](../00全流程SKILL/cinematic-director/references/continuity-bible.md#shot-to-shot-continuity-schema) 与 [State-change ledger](../00全流程SKILL/cinematic-director/references/continuity-bible.md#state-change-ledger)，每个段缝必须冻结 `in_state`、`out_state`、`cut_type`、`audio_bridge` 与 `owner`。任一项缺失或与通过审计的资产／连续性台账冲突时，退回修订，不发布采用分镜或提示词批次。

不得加载 00 包全文、风格库或示例库；用户明确选择风格时才读取单一对应风格 reference，调试、人工复核与统筹替换入口保持可用。
