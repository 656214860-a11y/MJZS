---
name: storyboard-prompt-render
displayName: 提示词渲染
description: 将定稿分镜翻译为生图/生视频可执行的提示词
stage: 分镜定稿
capabilities: [creative-writing, structured-output]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.renderPrompt, storyboard.validatePrompt]
dependsOn: [storyboard-shot-generation]
conflictsWith: []
parallelizable: true
paid: false
input: [shotChain, style, assets]
output: [imagePrompts, videoPrompts]
constraints: [风格一致性, 角色描述精确, 镜头语言准确, 负面提示词]
feedback:
  - onProgress: 更新三虎进度
  - onComplete: 通知并推进阶段
examples:
  - 用户："生成分镜提示词" → storyboard.renderPrompt()
---

## 说明
### 这个 SKILL 干什么
把分镜的每一镜渲染成「可以直接喂给生图模型」的图片提示词，并保证同一角色在不同镜头里
长相一致（一致性前缀 ＋ 镜头正文）。

### 具体做四件事
1. 每镜拼出提示词：角色一致性前缀 ＋ 场景与光线 ＋ 景别机位 ＋ 动作与表情 ＋ 画风与画质词。
2. 按目标模型调格式（逗号词组／自然语言句），并控住长度（别超模型上限）。
3. 挂上参考图槽位（有资产图时指定它作为参考，避免「换脸」）。
4. 输出提示词清单，供首帧管理页逐镜生成，也供你手工改词。

### 什么时候用它
- 分镜定稿、要批量出首帧之前（首帧／白模／视频生成都读这份提示词）。
- 想换画风或换生图模型时，重渲一遍提示词即可，不用重拆分镜。

### 输入／输出
- 输入：定稿分镜、一致性基线、资产参考图编号、目标生图模型与画风。
- 输出：每镜的图片提示词（含负向词）与参考图绑定关系。

### 用到的工具
- `storyboard.renderPrompts`：拼词与格式化。
- `storyboard.attachReferences`：绑定参考图。
- `storyboard.promptExport`：导出清单到项目。

### 约束与验收
- 同一角色跨镜的提示词前缀必须逐字一致，不靠模型「猜」。
- 提示词里不出现镜头编号等技术串（模型看不懂，还会污染画面）。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
