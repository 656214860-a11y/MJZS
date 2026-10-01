---
name: voice-emotion-check
displayName: 配音情感检查
description: 把配音与剧本的情绪标注逐句对一遍，偏差大的列出来
stage: 配音与字幕
capabilities: [vision, reasoning]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [voice.qualityCheck, subtitle.align]
dependsOn: [voice-tts-synthesis]
conflictsWith: []
parallelizable: true
paid: false
input: [audioTracks, script]
output: [emotionReport]
constraints: [逐句比对情绪标注, 偏差大的列出来, 不自动重录]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："这几句配音对不对味" → voice.checkEmotion({ shotIds })
  - 用户："哪句念得太平" → voice.compareScript({ shotIds })
---

## 说明
### 这个 SKILL 干什么
配音合成完了对一遍语气：剧本这一句标的是「压着怒」，出来的是不是念得很平。差得多的
列出来，重录不重录由你定——重录是要花钱的。

### 具体做四件事
1. 取标注：把剧本里逐句的情绪标注读出来。
2. 听成声：按句子边界切出每句的音轨。
3. 比一比：给每句的语速、音量与起伏打分，与标注比。
4. 出单子：偏差大的逐句列出，附建议（重录／调语速／改标注）。

### 什么时候用它
- 配音合成完，想知道哪几句不对味。
- 对白改了但只重录了几句，回头核对整体是否一致。

### 输入／输出
- 输入：音轨、剧本（含情绪标注）。
- 输出：情感检查报告（逐句）。

### 用到的工具
- `voice.qualityCheck`：09 配音与字幕 → 试听检查
- `subtitle.align`：字幕逐句对齐，跟着配音的时间轴走

### 约束与验收
- 不自动重录：重录是付费动作，单子出来等用户点。
- 拿不准的标「建议」：情感是创作判断，别当硬错。
- 句子边界要准：切错了先把切分报出来，别硬比。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
