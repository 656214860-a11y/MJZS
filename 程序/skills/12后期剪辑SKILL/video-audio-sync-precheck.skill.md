---
name: video-audio-sync-precheck
displayName: 音画同步预检
description: 剪辑合成前量一遍画面与声音的偏移，超阈值的镜头列出来
stage: 后期剪辑
capabilities: [vision, reasoning]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [subtitle.syncCheck, video.qualityCheck]
dependsOn: [video-quality-check, subtitle-auto-align]
conflictsWith: []
parallelizable: true
paid: false
input: [videoClips, audioTracks, subtitles]
output: [syncReport]
constraints: [偏移超阈值就报, 不自动裁剪, 结果可追溯]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："口型对不对得上" → video.precheckAudioSync({ videoIds })
  - 用户："哪几镜音画不同步" → video.reportOffset({ videoIds })
---

## 说明
### 这个 SKILL 干什么
剪辑合成前先量一遍：画面里的动作与声音的落点差了几帧。差得多的镜头列成一份单子，剪辑
一步照单子微调，而不是等成片出来才发现口型对不上。

### 具体做四件事
1. 取样点：按对白字头与画面动作找几个可比的时刻。
2. 量偏移：算出每一处的帧差。
3. 判阈值：超过约定阈值（默认 3 帧）的标出来。
4. 出报告：逐镜写明偏移量与参考时刻，附上建议的处理。

### 什么时候用它
- 视频、音轨和字幕就绪后，进剪辑合成之前先过一遍。
- 成片看着口型不对，回头定位是哪几镜。

### 输入／输出
- 输入：镜头编号、音轨。
- 输出：同步报告（逐镜偏移量与阈值判定）。

### 用到的工具
- `subtitle.syncCheck`：字幕落在本镜时长内、串行不重叠
- `video.qualityCheck`：视频生成 → 视频质检：时长／音轨／分辨率

### 约束与验收
- 只报不改：不自动裁剪、不自动拉伸，改由剪辑那一步做。
- 阈值与判定写清楚，别只给一个「好像有点偏」。
- 取不到可比点的镜头要标「无法判定」，不许猜一个数。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
