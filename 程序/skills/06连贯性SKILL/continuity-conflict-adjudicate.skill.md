---
name: continuity-conflict-adjudicate
displayName: 参考图冲突裁决
description: 一张参考图只能认一个职责：职责自相矛盾或两张图抢同一件事时给出优先级
stage: 连贯性清单
capabilities: [vision, reasoning]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [continuity.resolveConflict]
dependsOn: []
conflictsWith: []
parallelizable: false
paid: false
input: [shotRefs, referenceRoles, characterAnchor]
output: [conflictDecisions]
constraints: [一张参考图只认一个职责, 并列候选只给 2 个并写清推荐理由, 锚点字符串逐字复用]
feedback:
  - onProgress: 更新三虎进度
  - onError: 发现冲突或漂移时通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："这两张参考图谁说了算" → continuity.resolveConflict()
---

### 这个 SKILL 干什么
把「同一件事被两张参考图抢」理清楚：谁负责身份（面部、发型、服装），谁退成风格与光影补充，
结论写进 continuity_ledger.json 的 conflicts，供首帧与视频生成照着做。

### 具体做三件事
1. 逐镜读 character_refs 与 reference_roles，挑出「职责里混进了场景／动作／镜头」的自相矛盾项。
2. 按身份关键词（面部／发型／服装／瞳色／骨相／体型／标志）分组，同一组里多于一张图就是抢同一件事。
3. 并列候选不替用户定稿：给 2 个候选与各自的推荐理由，等用户在「04 连贯性清单」页面上点一下。

### 什么时候用它
- 初步分镜与资产清单都齐了之后、生成首帧之前。
- 用户反馈「同一角色两张脸」「场景跟着参考图乱跑」时，重新裁决一次。

### 输入／输出
- 输入：当前分镜 JSON 的 character_refs／reference_roles，资产清单里的 character_anchor。
- 输出：conflicts（每条含 shot_id、kind、priority 与 resolution）。

### 用到的工具
- `continuity.resolveConflict`：对着「04 连贯性清单」页面上的裁决条目执行。

### 约束与验收
- 不重写锚点字符串，只判优先级；被否掉的那一个写进 conflict_decisions。
- 每批次只问一次，问过就不再问。

## 说明

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与页面上的「手动生成连贯性清单」结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
