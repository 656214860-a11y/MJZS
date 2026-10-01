---
name: edit-bgm-sfx
displayName: 配乐与音效
description: 给成片配背景乐与动作音效，人声不被盖住
stage: 后期剪辑
capabilities: []
preferredModels: []
fallbackModels: []
tools: [edit.addBGM, edit.addSFX]
dependsOn: [edit-auto-compose]
conflictsWith: []
parallelizable: true
paid: false
input: [composedVideo, style, cues]
output: [mixedAudio]
constraints: [人声不被盖住, 音效与动作对齐, 版权可追溯]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："给成片配个背景乐" → edit.pickBGM({ mood })
  - 用户："混完之后台词听不清" → edit.mixAudio({ plan })
---

## 说明
### 这个 SKILL 干什么
配乐定情绪、音效给质感，前提是别把台词糊掉。这一步按情绪曲线挑曲子，按动作点摆音效，
混完再量一遍人声是不是还在最前面。

### 具体做四件事
1. 定基调：按情绪曲线选曲风与段落（起、推、收）。
2. 摆音效：按动作点对齐脚步、开门、打击等点。
3. 混音：人声轨留出余量，配乐自动让路（对白处压低）。
4. 量一遍：混完检查人声与配乐的电平差，不够就再让一点。

### 什么时候用它
- 粗剪有了画面，要配声音。
- 成片里台词听不清，回头压一压配乐。

### 输入／输出
- 输入：粗剪成片、风格设定、动作点清单。
- 输出：混好的音轨。

### 用到的工具
- `edit.addBGM`：10 后期剪辑 → 背景音乐
- `edit.addSFX`：10 后期剪辑 → 音效

### 约束与验收
- 人声第一：任何盖住台词的配乐都要压下去。
- 音效对齐动作点：差得多的挪到最近的拍上。
- 版权可追溯：用的曲子要记来源与许可。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
