---
name: firstframe-quality
displayName: 首帧质量检查
description: 生成后质检，低分自动重生成
stage: 首帧管理
capabilities: [vision]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [firstframe.qualityCheck]
dependsOn: [firstframe-batch]
conflictsWith: []
parallelizable: true
paid: false
input: [frameIds]
output: [scored, lowQuality]
constraints: [清晰度、角色一致性、风格一致性]
feedback:
  - onProgress: 更新三虎进度
  - onComplete: 低分项自动重生成或通知
examples:
  - 输入帧 → firstframe.qualityCheck({ frameIds })
---

## 说明
### 这个 SKILL 干什么
给出好的首帧做一次质量检查：清不清楚、像不像这个角色、画风对不对、有没有明显错手错脸，
低分的挑出来重生成。

### 具体查四件事
1. 技术项：分辨率、是否糊、有没有裁掉头脚、纯色／空白。
2. 角色一致性：与资产参考图比对五官、发型、服装配色。
3. 画风一致性：与本集其它首帧比对色调与画质。
4. 构图可用性：主体位置与朝向能不能接上后面的运镜与动作。

### 什么时候用它
- 批量出完首帧之后（准备交去做视频之前）。
- 发现某几镜成片「不像同一个人」时，回头单独查那几镜。

### 输入／输出
- 输入：首帧图（按镜头号）。
- 输出：每镜得分与低分清单（含原因），供重生成或手工替换。

### 用到的工具
- `firstframe.qualityCheck`（06 首帧管理 → 质量检查）

### 约束与验收
- 只判「能不能用」，不改图。
- 低分项给的是可动手的结论（重生成／换参考图／改提示词），不是一句「质量不佳」。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
