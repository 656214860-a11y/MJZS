---
name: storyboard-final-validate
displayName: 定稿校验
description: 按交付契约校验字段完整性、编号唯一与路径合法性，通过才准采用
stage: 分镜定稿
capabilities: [reasoning, structured-output]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.validate, storyboard.checkDrift]
dependsOn: [storyboard-asset-sync]
conflictsWith: []
parallelizable: true
paid: false
input: [syncedStoryboard]
output: [validationReport]
constraints: [字段完整, 镜头编号唯一, 通过才准采用]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："这份定稿能用吗" → storyboard.validateFinal({ source })
  - 用户："镜头编号有没有重的" → storyboard.checkContract({ source })
---

## 说明
### 这个 SKILL 干什么
定稿的最后一道闸：字段齐不齐、镜头编号重没重、首帧与资产的路径能不能解析、时长在不在
范围内。过不了就列出来，不许带病采用。

### 具体做四件事
1. 查字段：镜头编号、内容、时长、对白、提示词逐项检查。
2. 查唯一：镜头编号重复直接拦下。
3. 查路径：首帧与资产引用的路径落在项目内且能解析。
4. 出报告：通过的放行；不通过的按「硬错／提醒」分开列，硬错一条都不许采用。

### 什么时候用它
- 「同步资产 · 生成定稿」之前先自检一遍。
- 接手别人做的分镜，先看这份能不能用。

### 输入／输出
- 输入：对齐后的分镜 JSON。
- 输出：校验报告（硬错与提醒分开）。

### 用到的工具
- `storyboard.validate`：镜头链契约校验：字段、编号、路径
- `storyboard.checkDrift`：05 分镜定稿 → 检查漂移

### 约束与验收
- 硬错一条都不放行：宁可不采用，也不许带病往下走。
- 提醒只报不拦（比如提示词偏短），但要在报告里写清。
- 校验不改文件：报告出来，改由用户在前面的步骤做。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
