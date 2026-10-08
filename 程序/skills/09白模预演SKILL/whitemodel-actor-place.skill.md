---
name: whitemodel-actor-place
displayName: 人物走位
description: 按分镜给人物排站位与走位，避免穿模与视线打架
stage: 白模预演
capabilities: []
preferredModels: []
fallbackModels: []
tools: [whitemodel.placeActors, whitemodel.buildScene]
dependsOn: [whitemodel-scene-build]
conflictsWith: []
parallelizable: true
paid: false
input: [sceneJson, adoptedStoryboard]
output: [blockingPlan]
constraints: [站位不穿模, 视线方向明确, 与分镜一致]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："给这一场排一下站位" → whitemodel.placeActors({ sceneId })
  - 用户："两个人是不是站太近了" → whitemodel.checkSpacing({ sceneId })
---

## 说明
### 这个 SKILL 干什么
白模里最先要定的是人站哪儿、往哪儿看、什么时候动。这一步按分镜的人物与动作排一份
站位表，顺带查一遍人和人、人和景有没有撞在一起。

### 具体做四件事
1. 读分镜：把每镜的出场人物、动作起止与视线方向抄下来。
2. 排站位：一人一个位置，标上朝向与间距。
3. 排走位：写明从哪儿走到哪儿、用几拍走完。
4. 查碰撞：人和人、人和景的最小间距不够就报出来，给替代位置。

### 什么时候用它
- 白模搭完景，要往里摆人。
- 预演看下来发现有人挡住了主角。

### 输入／输出
- 输入：场景工程、已采用分镜。
- 输出：站位与走位方案（含间距检查结果）。

### 用到的工具
- `whitemodel.placeActors`：07 白模预演 → 人物走位
- `whitemodel.buildScene`：07 白模预演 → 开始制作

### 约束与验收
- 站位跟着分镜走：分镜写「背对镜头」就不许摆成正脸。
- 撞了要报，不许悄悄挪一个人的位置了事——挪动要写在表里。
- 不许把同一套走位套给全部镜头。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
