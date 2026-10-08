---
name: subtitle-auto-align
displayName: 字幕自动对齐
description: 根据配音自动拆句、逐句对齐字幕，音画同步检查
stage: 配音与字幕
capabilities: []
preferredModels: []
fallbackModels: []
tools: [subtitle.generate, subtitle.align, subtitle.syncCheck]
dependsOn: [voice-tts-synthesis]
conflictsWith: []
parallelizable: true
paid: false
input: [audioTracks, script]
output: [subtitleFile, syncReport]
constraints: [逐句对齐, 音画同步, 支持 SRT/ASS 格式]
feedback:
  - onProgress: 更新三虎进度
  - onError: 同步异常通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："生成字幕" → subtitle.generate()
---

## 说明
### 这个 SKILL 干什么
按配好的音轨拆句、逐句对齐字幕，做一次音画同步检查，输出 SRT／ASS，供剪辑与交付。

### 具体做四件事
1. 拆句：按对白与停顿把长句切成字幕行，一行不超过可读长度。
2. 对齐：给每行算入点与出点（贴到配音的起止），逐句而不是整段估。
3. 同步检查：逐句比对音频与字幕的时间差，超阈值的标出来。
4. 导出：生成 SRT 与 ASS（含样式），放进项目字幕目录。

### 什么时候用它
- 配音跑完之后（09 配音与字幕页）。
- 成片字幕与声音对不上时，重跑一次对齐。

### 输入／输出
- 输入：音轨（按镜头）、剧本对白。
- 输出：字幕文件（SRT／ASS）与同步报告。

### 用到的工具
- `subtitle.generate`／`subtitle.align`／`subtitle.syncCheck`

### 约束与验收
- 逐句对齐，不许整段平均分。
- 一个字幕行不跨镜；跨镜的先拆。
- 同步误差超过阈值要报出来，不静默放过。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
