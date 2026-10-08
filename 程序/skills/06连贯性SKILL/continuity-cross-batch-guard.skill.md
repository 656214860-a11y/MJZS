---
name: continuity-cross-batch-guard
displayName: 跨批次连续性
description: 同一个锚点在两批之间必须一模一样：服装、光源方向与空间位置都不许漂
stage: 连贯性清单
capabilities: [structured-output, reasoning]
preferredModels: [qwen-max, deepseek-v4-pro]
fallbackModels: [deepseek-v4-flash]
tools: [continuity.checkCrossBatch]
dependsOn: [continuity-anchor-freeze]
conflictsWith: []
parallelizable: false
paid: false
input: [frozenAnchors, shotBatches]
output: [crossBatchReport]
constraints: [只比字符串不重新描述, 每一批都要参与比对, 不一致就必须报出来]
feedback:
  - onProgress: 更新三虎进度
  - onError: 发现冲突或漂移时通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："跨批次会不会漂" → continuity.checkCrossBatch()
---

### 这个 SKILL 干什么
把同一件事在不同批次之间的锚点摆在一起比：角色服装、场景光源方向、空间锚点与道具尺度，
只要两批的字符串不一样就是漂了，结论写进 continuity_ledger.json 的 cross_batch。

### 具体做四件事
1. 按批次收集冻结锚点（kind＋id＋state 为键）。
2. 同一个键在多批之间出现两种以上字符串时，记成不一致并写清每批各是什么。
3. 分镜里显式写过的 continuity_flags 也一并带进结论，标成「全程必须保住」。
4. 比完只报结论，不改锚点——改锚点要走资产页，改批次要走分镜定稿页。

### 什么时候用它
- 冻结锚点之后、分镜定稿与首帧生成之前；中途改了资产或重切了批次，再跑一次。

### 输入／输出
- 输入：冻结锚点清单、批次划分。
- 输出：cross_batch（kind／id／state／ok／detail）。

### 用到的工具
- `continuity.checkCrossBatch`：对着「04 连贯性清单」页面上的清单表执行。

### 约束与验收
- 只比字符串，不许重新描述锚点（硬约束 4）。
- 一条不一致就是一条待办，不许笼统写「可能漂移」。

## 说明

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与页面上的「手动生成连贯性清单」结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
