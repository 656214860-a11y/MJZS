---
name: continuity-triplet-check
displayName: 三元组校验
description: 同一批次内 scene_id＋character_ids＋costume_id 必须一致，不一致就重切批次
stage: 连贯性清单
capabilities: [structured-output]
preferredModels: [deepseek-v4-pro, qwen-max]
fallbackModels: [deepseek-v4-flash]
tools: [continuity.checkTriplets]
dependsOn: [continuity-cross-batch-guard]
conflictsWith: []
parallelizable: false
paid: false
input: [shotBatches, sceneId, characterIds, costumeId]
output: [tripletReport]
constraints: [一批一个三元组, 不一致不许静默放行, 只读不改批次划分]
feedback:
  - onProgress: 更新三虎进度
  - onError: 发现冲突或漂移时通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："这批镜头的三元组对不对" → continuity.checkTriplets()
---

### 这个 SKILL 干什么
批次划分的硬标准：同一批次里所有镜头的场景、角色集合与服装状态必须是同一个组合。
对得上才算合规，对不上就写清有几种组合，让用户在分镜定稿页重切批次。

### 具体做三件事
1. 按批次收集每镜的 (scene_id, character_ids, costume_id)。
2. 去重后只留一种就是一致；多于一种就写「同一批次里出现 N 种三元组，必须重切批次」。
3. 结论与批次编号一起写进 continuity_ledger.json 的 triplets，三元组字典同步到 _shared/triplets。

### 什么时候用它
- 批次切完之后立刻跑一次；重做提示词或替换资产之后再跑一次。

### 输入／输出
- 输入：批次划分与每镜的三元组。
- 输出：triplets（batch_id／ok／scene_id／character_ids／costume_id／detail）。

### 用到的工具
- `continuity.checkTriplets`：对着「04 连贯性清单」页面上的校验表执行。

### 约束与验收
- 只读不改：批次怎么切由分镜定稿决定，这里只判合规。
- 不合规必须是一条待办，不许只写「建议检查」。

## 说明

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与页面上的「手动生成连贯性清单」结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
