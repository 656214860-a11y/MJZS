---
name: edit-transition-library
displayName: 转场库
description: 按风格与剧情需要挑转场并摆进去，不盖对白、不重复用同一种
stage: 后期剪辑
capabilities: []
preferredModels: []
fallbackModels: []
tools: [edit.addTransition, edit.compose]
dependsOn: [edit-auto-compose]
conflictsWith: []
parallelizable: true
paid: false
input: [composedVideo, style]
output: [transitionPlan]
constraints: [转场不盖对白, 同段落不重复同一种, 时长可控]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把接点处理得顺一点" → edit.applyTransition({ plan })
  - 用户："都有哪些转场能用" → edit.listTransitions({ style })
---

## 说明
### 这个 SKILL 干什么
自动粗剪摆出来的接点未必好看。这一步按风格与剧情挑转场：硬切为主，情绪拐弯处才给一个
像样的，且不许压在对白上。

### 具体做四件事
1. 列接点：把每一处镜头衔接找出来，标上情绪拐弯与时间跳变。
2. 配转场：默认硬切；拐弯处给叠化或划像，动作接动作的用匹配剪。
3. 避对白：转场落在对白上的挪开。
4. 查重复：同一段落里不许连着用两遍同一种转场。

### 什么时候用它
- 粗剪出来了，接点生硬。
- 同一段落里连着好几处叠化，看着发腻。

### 输入／输出
- 输入：粗剪成片、风格设定。
- 输出：转场方案（逐接点）。

### 用到的工具
- `edit.addTransition`：10 后期剪辑 → 转场
- `edit.compose`：10 后期剪辑 → 自动合成

### 约束与验收
- 转场不盖对白：压住台词的转场一律挪开或延长。
- 少用为佳：默认硬切，能不加就不加。
- 改动只落在剪辑方案上，原片不动。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
