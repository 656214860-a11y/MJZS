---
name: script-emotion-curve
displayName: 情绪曲线标注
description: 给每一场标出情绪强度与转折点，落成一条可核对的情绪曲线
stage: 剧本准备
capabilities: [reasoning, structured-output]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [script.validate, script.save]
dependsOn: []
conflictsWith: []
parallelizable: true
paid: false
input: [scriptRaw]
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
把整集的情绪走势画成一条曲线：按全片 12 个关键节拍量化 0～10 的张力，并把每个节拍映射到
具体场次、钩子与转折句。分镜与配音都按这条曲线决定镜头长短与语气，所以它只标注、不改词。

### 具体做四件事
1. 对齐节拍：按故事因果定位 12 个关键节拍，并映射回具体场次。
2. 标强度：按 0～10 给每个节拍量化张力，并写明它承担的戏剧任务。
3. 找转折：标出每个节拍对应的钩子位置与转折句；第 9 节拍须为全片最高峰且不低于 9.5。
4. 校曲线：至少两次波峰达到 9.0，峰间必须有可解释的回落，拒绝持续平庸或持续高压；不再以“相邻场次不得跳两级”替代节拍判定。

### 什么时候用它
- 拆分镜之前对一遍节奏，避免整集一条平线。
- 某几场看起来「闷」，要定位是哪一段没有起伏。

### 输入／输出
- 输入：本阶段自然剧本的场次。
- 输出：情绪曲线（12 节拍强度 ＋ 戏剧任务）、节拍表（场次映射与钩子位置）。
- 落盘：output/emotion_curve.json（每个节拍一条，编号 EC_###，强度字段遵循现有 JSON 契约）。

### 用到的工具
- `script.validate`：读剧本的场次与时间码，落成可核对的曲线
- `script.save`：01 剧本准备 → 保存剧本

### 约束与验收
- 只标注不改词：台词与场次一个字都不动。
- 强度要能对上戏：写不出理由的分数就是拍脑袋，报出来。
- 钩子位置要落到具体句子，不许写「本场后段」。
- 定向依据：仅按需读取 [emotion-beat-curve.md 的 12 关键节拍点量化模型与剧本含金量判定法则](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/emotion-beat-curve.md#一-12-关键节拍点量化模型010-分)。不得全文注入 00 包或加载无关风格／示例 reference。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
