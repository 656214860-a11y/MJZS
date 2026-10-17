---
name: storyboard-camera-language
displayName: 镜头语言设计
description: 为镜头链设计景别、角度与运镜，保证多样且服务叙事
stage: 初步分镜
capabilities: [creative-writing, structured-output]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.pacingCheck, storyboard.renderPrompt]
dependsOn: [storyboard-shot-generation]
conflictsWith: []
parallelizable: true
paid: false
input: [shotChain, style]
output: [cameraPlan]
constraints: [景别与角度多样, 运动服务叙事, 不越轴线]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："给这一场配上镜头语言" → storyboard.designCamera({ sceneId })
  - 用户："是不是连着好几镜都是近景" → storyboard.checkVariety({ episodeId })
---

## 说明
### 这个 SKILL 干什么
给已经拆好的镜头链补上镜头语言：每一镜用什么景别、什么角度、怎么运动，为什么这么选。
目标是同一场里不连着三镜一个样，也不为了花哨而乱动。

### 具体做四件事
1. 定基调：按这一场的情绪强度决定整体是稳、是压、还是动。
2. 配景别：远中近特交替，同景别不连用三镜以上。
3. 配运动：推、拉、摇、移、跟各按叙事需要用，静止也要写明理由。
4. 查轴线：对视、走位与越肩的三处轴线逐场校一遍。

### 什么时候用它
- 镜头链有了但看起来「平」，要补镜头语言。
- 发到生成模型之前，先确认景别与运动写得可执行。

### 输入／输出
- 输入：镜头链、画风与情绪曲线。
- 输出：镜头语言方案（每镜的景别、角度、运动与理由）。

### 用到的工具
- `storyboard.pacingCheck`：03 初步分镜 → 分镜提示词生成／节奏检查
- `storyboard.renderPrompt`：07 分镜定稿 → 生成提示词（把景别与运镜写进提示词）

### 约束与验收
- 运动要有理由：写不出理由的运镜一律改成静止。
- 轴线不越：真需要越轴就写清用哪一镜过渡。
- 术语用行业话（远中近特、推拉摇移跟），别写「拍得酷一点」。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
