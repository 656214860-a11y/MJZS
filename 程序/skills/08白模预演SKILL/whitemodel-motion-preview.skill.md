---
name: whitemodel-motion-preview
displayName: 运镜与节奏预演
description: 在白模中录制运镜路径、动作关键帧、时长节奏
stage: 白模预演
capabilities: []
preferredModels: []
fallbackModels: []
tools: [whitemodel.recordCamera, whitemodel.recordMotion, whitemodel.validateRhythm]
dependsOn: [whitemodel-scene-build]
conflictsWith: []
parallelizable: true
paid: false
input: [sceneJson, shotChain]
output: [previewVideo, motionData, rhythmReport]
constraints: [运镜路径平滑, 动作关键帧完整, 节奏与分镜匹配]
feedback:
  - onProgress: 更新三虎进度
  - onError: 节奏异常通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："录制运镜预演" → whitemodel.recordCamera()
---

## 说明
### 这个 SKILL 干什么
在白模里把运镜与动作演一遍，录成预演片，并核一下节奏：镜头长度、动作起止、转场点
是不是和分镜对得上。

### 具体做四件事
1. 记录运镜：推／拉／摇／移／跟的路径与速度，逐镜存成关键帧。
2. 记录动作：人物起止姿势与中间关键帧。
3. 校验节奏：整场时长、每镜时长与分镜的出入，指出拖或赶的地方。
4. 出预演片：按镜头顺序合成一版带时长标注的预览。

### 什么时候用它
- 白模搭好之后、正式出首帧／视频之前。
- 成片觉得「节奏不对」时，回白模里量一遍再做取舍。

### 输入／输出
- 输入：场景 JSON、镜头链。
- 输出：预演视频、运镜与动作数据、节奏报告。

### 用到的工具
- `whitemodel.recordCamera`／`whitemodel.recordMotion`（预演录制）
- `whitemodel.validateRhythm`（节奏校验）

### 约束与验收
- 运镜路径平滑，不出现抖动与急停（这是能不能拿去生成视频的前提）。
- 动作关键帧完整：起、止与中间姿态都要有。
- 节奏以分镜时长为准，白模改动要能回到分镜里。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
