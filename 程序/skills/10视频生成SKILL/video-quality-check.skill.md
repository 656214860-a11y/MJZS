---
name: video-quality-check
displayName: 视频质检
description: 视频生成后质检，低分自动重生成或提示用户
stage: 视频生成
capabilities: [vision]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [video.qualityCheck]
dependsOn: [video-batch-submit]
conflictsWith: []
parallelizable: true
paid: false
input: [videoIds]
output: [scored, lowQuality]
constraints: [清晰度、角色一致性、风格一致性、音画同步预检]
feedback:
  - onProgress: 更新三虎进度
  - onComplete: 低分项自动重生成或通知
examples:
  - 输入视频 → video.qualityCheck({ videoIds })
---

## 说明
### 这个 SKILL 干什么
看成片能不能用：清晰度、角色一致性、风格一致性、音画同步预检，低分的挑出来重生成，
或者摆给你看一眼再决定。

### 具体查五件事
1. 技术项：分辨率、码率、时长、有没有音轨（用 ffprobe 量，不靠肉眼）。
2. 画面稳定性：有没有糊帧、闪烁、撕裂、明显变形。
3. 角色一致性：与首帧／资产参考图比对，确认没有换脸换装。
4. 风格一致性：与本集其它镜头比对色调与画质。
5. 音画同步预检：对白与口型的粗对齐（真正对齐由字幕那一步做细）。

### 什么时候用它
- 视频下载完之后、验收之前（「自动验收」开着时它就是那道闸）。
- 觉得某个镜头「怪怪的」时单独查那一镜。

### 输入／输出
- 输入：成片（按镜头号）。
- 输出：每镜得分与低分清单（含原因），供重生成或人工复核。

### 用到的工具
- `video.qualityCheck`（10 视频生成 → 质量检查）

### 约束与验收
- 技术质检不通过的不许进入验收（页面上的「通过」会被拦下）。
- 低分项给出可动手的下一步（重生成／换首帧／改提示词）。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
