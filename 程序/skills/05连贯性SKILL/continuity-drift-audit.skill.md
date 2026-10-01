---
name: continuity-drift-audit
displayName: 锚点漂移审计
description: 台账冻结的锚点与资产里现在的锚点对不上就报警：谁改过、改成什么
stage: 连贯性清单
capabilities: [structured-output, reasoning]
preferredModels: [deepseek-v4-pro, qwen-max]
fallbackModels: [deepseek-v4-flash]
tools: [continuity.buildLedger, continuity.auditDrift]
dependsOn: [continuity-anchor-freeze]
conflictsWith: []
parallelizable: false
paid: false
input: [ledger, assets, characterAnchor]
output: [driftReport]
constraints: [只比字符串不重新描述, 逐条写清冻结值与现值, 没台账就先算一份]
feedback:
  - onProgress: 更新三虎进度
  - onError: 发现冲突或漂移时通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："资产改过之后有没有漂" → continuity.auditDrift()
---

### 这个 SKILL 干什么
盯住「冻过的东西被人改过」这件事：台账里的角色锚点与资产清单里现在的锚点逐条比字符串，
对不上就写清冻结值、现值与是哪一号角色／哪个状态，结论写进 continuity_ledger.json 的 drift。

### 具体做三件事
1. 读回 03_continuity/output/continuity_ledger.json；没有台账就先按当前分镜与资产算一份。
2. 逐条比角色锚点（带服装状态覆盖）：字符串不同就是漂移。
3. 漂移进待办（门禁 G-09），并在「04 连贯性清单」页面上写成一行看得懂的结论。

### 什么时候用它
- 首帧或视频生成之前；资产清单被改过、或某一批偷偷重写了锚点之后。

### 输入／输出
- 输入：台账、资产清单里的 character_anchor。
- 输出：drift（kind／id／state／ok／detail）。

### 用到的工具
- `continuity.buildLedger`：现场算一份台账并落盘（本机跑得完，不调外部模型）。
- `continuity.auditDrift`：对着「04 连贯性清单」页面上的校验表执行。

### 约束与验收
- 只比字符串，不重新描述锚点，也不自作主张改资产。
- 结论里必须同时有「冻结的是什么」与「现在是什么」。

## 说明

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与页面上的「手动生成连贯性清单」结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
