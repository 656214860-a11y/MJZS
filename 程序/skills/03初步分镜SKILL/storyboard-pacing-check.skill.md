---
name: storyboard-pacing-check
displayName: 节奏与连续性检查
description: 检查分镜的节奏曲线、场景连续性、角色出场频率、动作衔接
stage: 初步分镜
capabilities: [reasoning, structured-output]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.pacingCheck, storyboard.continuityCheck]
dependsOn: [storyboard-shot-generation]
conflictsWith: []
parallelizable: true
paid: false
input: [shotChain]
output: [pacingReport, continuityIssues]
constraints: [节奏曲线可视化, 连续性问题标注, 建议修改点]
feedback:
  - onProgress: 更新三虎进度
  - onError: 发现问题时通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："检查分镜节奏" → storyboard.pacingCheck()
---

## 说明
### 这个 SKILL 干什么
给已经拆好的分镜做一次「读起来顺不顺」的检查：节奏、连续性与轴线，只报告不改稿，
供你在分镜定稿前决定改哪几镜。

### 具体查四类问题
1. 节奏：连续三镜景别相同、连续两镜时长雷同、整场没有停顿或爆点。
2. 连续性：轴线跳（人物左右互换）、视线不接、持物忽然出现或消失、服装／天气对不上。
3. 空间：同一场里景别跨度过大（远直接切特写）又没给过渡镜。
4. 收尾：场与场之间的钩子有没有落空。

### 什么时候用它
- 分镜生成完，定稿之前先跑一遍。
- 每次改完几镜之后再跑一遍，确认没有引入新的跳轴。

### 输入／输出
- 输入：镜头链 JSON（当前分镜文件）。
- 输出：问题清单（镜头号 ＋ 类别 ＋ 说明 ＋ 建议），不改原稿。

### 用到的工具
- `storyboard.pacingCheck`：算节奏与重复度。
- `storyboard.continuityCheck`：查轴线、视线、持物。

### 约束与验收
- 只报告，不自动改分镜：改哪一镜由用户拍板。
- 每条问题都要指到具体镜头号，不给「整体节奏偏慢」这种没法动手的结论。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
