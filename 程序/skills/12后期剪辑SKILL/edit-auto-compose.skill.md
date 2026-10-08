---
name: edit-auto-compose
displayName: 自动合成与转场
description: 自动合成视频片段、添加转场、音效、背景音乐
stage: 后期剪辑
capabilities: []
preferredModels: []
fallbackModels: []
tools: [edit.compose, edit.addTransition, edit.addSFX, edit.addBGM]
dependsOn: [video-quality-check, subtitle-auto-align]
conflictsWith: []
parallelizable: false
paid: false
input: [videoClips, audioTracks, subtitleFile, style]
output: [composedVideo]
constraints: [转场自然, 音画同步, 风格统一]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试
  - onComplete: 通知并推进阶段
examples:
  - 用户："合成成片" → edit.compose()
---

## 说明
### 这个 SKILL 干什么
把通过质检的镜头按顺序合起来：拼接、转场、音效与背景音乐，出一版完整成片。

### 具体做四件事
1. 取素材：优先用「已下载＋质检通过＋已验收」的那一版（与自动粗剪同一口径）。
2. 拼接：按镜头编号顺序接，处理时长与首尾帧的衔接。
3. 加转场与声音：按分镜的情绪标记挑转场，铺音效与背景音乐，音量压到不盖对白。
4. 出成片：按时长与分辨率要求合成，落进项目的成片目录。

### 什么时候用它
- 后期剪辑页点「手动制作剪辑」（或「自动剪辑勾选镜头」只做勾上的那几镜）。
- 换了某几个镜头的成片后，重新合成一版。

### 输入／输出
- 输入：镜头成片、音轨、字幕、风格设定（转场与音乐）。
- 输出：合成成片。

### 用到的工具
- `edit.compose`／`edit.addTransition`／`edit.addSFX`／`edit.addBGM`
- 底层走本机 ffmpeg（设置里选程序位置）。

### 约束与验收
- 缺料不硬拼：没有可用版本的镜头会被跳过并列出原因（不静默丢镜头）。
- 转场自然、音画同步；音量不盖对白。
- 同一版成片可重复生成，结果一致（幂等）。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
