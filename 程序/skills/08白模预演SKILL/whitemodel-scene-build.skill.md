---
name: whitemodel-scene-build
displayName: 白模搭景与调度
description: 基于分镜生成 3D 白模场景，固定空间、走位、朝向
stage: 白模预演
capabilities: []
preferredModels: []
fallbackModels: []
tools: [whitemodel.buildScene, whitemodel.placeActors, whitemodel.setCamera]
dependsOn: [storyboard-shot-generation]
conflictsWith: []
parallelizable: false
paid: false
input: [shotChain, sceneList, characterProfiles]
output: [sceneJson, whiteModelVideo]
constraints: [空间关系准确, 走位路径合理, 人物朝向明确]
feedback:
  - onProgress: 更新三虎进度
  - onComplete: 通知并推进阶段
examples:
  - 用户："搭白模场景" → whitemodel.buildScene()
---

## 说明
### 这个 SKILL 干什么
按分镜搭一版三维白模（灰模）：把空间、人物走位与朝向先摆正，用来提前检查调度——
白模对了，后面出图与出视频才不会出现「人从墙里穿过去」。

### 具体做四件事
1. 建空间：按分镜里的场景生成地面、主要墙体与体块。
2. 摆人物：按每镜的站位与走位把替身放到位，方向按视线定。
3. 架相机：按每镜的机位与景别摆相机，焦距与高度对齐分镜。
4. 出白模小样：按镜头逐条渲染，供你对着分镜核对调度。

### 什么时候用它
- 白模预演页点「手动制作白模」。
- 分镜里空间复杂（多人、多房间）时先跑白模，比直接出图便宜得多。

### 输入／输出
- 输入：镜头链、场景清单、人物外形与身高设定。
- 输出：场景 JSON（体块／替身／相机）与白模预览视频。

### 用到的工具
- `whitemodel.buildScene`：搭景（Blender 本体在工作流里跑）。
- `whitemodel.placeActors`：摆人物与走位。
- `whitemodel.setCamera`：架相机。

### 约束与验收
- 空间关系以分镜为准，不自作主张改布局。
- 走位路径要绕开实体，不许穿模。
- 这一步不花钱（本地渲染），但耗时间：按镜头数估时间再开跑。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
