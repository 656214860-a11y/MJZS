---
name: whitemodel-rhythm-check
displayName: 白模节奏检查
description: 把白模动作的节拍与对白、情绪曲线对一遍，定位到帧
stage: 白模预演
capabilities: [reasoning]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [whitemodel.validateRhythm, whitemodel.recordMotion]
dependsOn: [whitemodel-motion-preview]
conflictsWith: []
parallelizable: true
paid: false
input: [motionData, rhythmReport]
output: [rhythmIssues]
constraints: [动作节拍与对白对齐, 过场不拖, 问题定位到帧]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："白模这段节奏对不对" → whitemodel.validateRhythm({ shotIds })
  - 用户："哪里拖了" → whitemodel.checkPacing({ shotIds })
---

## 说明
### 这个 SKILL 干什么
白模跑完之后对节拍：动作的起落与对白的字头对不对得上、两镜之间的过场拖不拖、整段
有没有「人已经站好了还在等」的空档。

### 具体做四件事
1. 对字头：把动作关键帧与对白时间码摆在一起比。
2. 看过场：两镜之间衔接超过 12 帧还在原地就报。
3. 排空档：整段没有动作也没有对白的时段列出来。
4. 出问题单：每条写明在哪一镜、第几帧、差多少、建议怎么改。

### 什么时候用它
- 白模小片看完，觉得「哪里怪但说不上来」。
- 进视频生成之前先排一遍空档与拖沓。

### 输入／输出
- 输入：动作数据、运镜与节奏预演的结果。
- 输出：节奏问题单（定位到镜与帧）。

### 用到的工具
- `whitemodel.validateRhythm`：07 白模预演 → 节奏检查
- `whitemodel.recordMotion`：07 白模预演 → 录制动作

### 约束与验收
- 只说问题不自动改工程：改哪一镜由用户点头。
- 定位要到帧：写「第 3 镜 42 帧」而不是「中段有点慢」。
- 节拍是创作判断，拿不准的标成「建议」，别当硬错拦下。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
