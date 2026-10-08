---
name: firstframe-auto-fill
displayName: 缺帧自动补
description: 无人值守地把缺首帧的镜头排队生成，不碰已有的
stage: 首帧管理
capabilities: [structured-output]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [firstframe.batchGenerate, firstframe.retry]
dependsOn: [firstframe-batch, storyboard-asset-sync]
conflictsWith: []
parallelizable: true
paid: true
input: [projectId, scope]
output: [submitted, skipped]
constraints: [只补缺首帧的, 幂等键不重复提交, 付费前确认]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："缺首帧的镜头全补上" → firstframe.autoFill({ scope })
  - 用户："还有哪几镜没首帧" → firstframe.checkMissing({ projectId })
---

## 说明
### 这个 SKILL 干什么
「自动补首帧」的无人值守档：算出哪些镜头还没有可用首帧，按清单排队生成，跑完把成功与
跳过分别报出来。已经就绪的、被用户手动跳过的都不碰。

### 具体做四件事
1. 算缺口：首帧文件不在、或已标记删除的镜头。
2. 排次序：按镜头号排，先把这一批做完再动下一批。
3. 排队生成：逐镜提交，带上幂等键，断点续跑。
4. 报账：提交几镜、跳过几镜（各写原因）、还差几镜。

### 什么时候用它
- 第 05 步把「自动补首帧」打开之后自动跑。
- 中途加了新镜头，重新补一轮缺口。

### 输入／输出
- 输入：项目、补哪些（缺口／指定镜头）。
- 输出：已提交、已跳过（含原因）。

### 用到的工具
- `firstframe.batchGenerate`：06 首帧管理 → 手动制作首帧
- `firstframe.retry`：06 首帧管理 → 重试失败项

### 约束与验收
- 只补缺的：已有首帧的镜头绝不重生成。
- 花钱的活先问一句：不在预算内就停下来。
- 用户手动跳过的镜头要记住，别下一轮又给勾回来。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
