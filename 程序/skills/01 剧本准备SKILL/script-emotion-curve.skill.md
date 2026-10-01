---
name: script-emotion-curve
displayName: 情绪曲线标注
description: 给每一场标出情绪强度与转折点，落成一条可核对的情绪曲线
stage: 剧本准备
capabilities: [reasoning, structured-output]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [script.validate, script.save]
dependsOn: [script-structured-generation]
conflictsWith: []
parallelizable: true
paid: false
input: [structuredScript]
output: [emotionCurve, beatSheet]
constraints: [每场标强度, 曲线与钩子对齐, 不改台词]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："给这一集标个情绪曲线" → script.markEmotionCurve({ episodeId })
  - 用户："哪几场太平了" → script.validateCurve({ episodeId })
---

## 说明
### 这个 SKILL 干什么
把整集的情绪走势画成一条曲线：每场给一个 1～10 的强度，标出起、承、转、合与钩子落在
哪一句上。分镜与配音都按这条曲线决定镜头长短与语气，所以它只标注、不改词。

### 具体做四件事
1. 读场次：按剧本的场次顺一遍故事线。
2. 标强度：每场给一个 1～10 的强度，并写一句为什么。
3. 找转折：标出每场的钩子位置与转折句。
4. 校曲线：相邻两场强度不许跳两级以上（真跳了要写明理由）。

### 什么时候用它
- 拆分镜之前对一遍节奏，避免整集一条平线。
- 某几场看起来「闷」，要定位是哪一段没有起伏。

### 输入／输出
- 输入：结构化剧本。
- 输出：情绪曲线（每场强度 ＋ 理由）、节拍表（起承转合与钩子位置）。
- 落盘：output/emotion_curve.json（每场一条，编号 EC_###，强度 1～10）。

### 用到的工具
- `script.validate`：读剧本的场次与时间码，落成可核对的曲线
- `script.save`：01 剧本准备 → 保存剧本

### 约束与验收
- 只标注不改词：台词与场次一个字都不动。
- 强度要能对上戏：写不出理由的分数就是拍脑袋，报出来。
- 钩子位置要落到具体句子，不许写「本场后段」。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
