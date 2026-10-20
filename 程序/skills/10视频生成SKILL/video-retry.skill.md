---
name: video-retry
displayName: 失败视频重试
description: 只把提交失败或跑挂的镜头重跑，已成功的不重复提交
stage: 视频生成
capabilities: []
preferredModels: []
fallbackModels: []
tools: [video.retry, video.batchSubmit]
dependsOn: [video-batch-submit]
conflictsWith: []
parallelizable: true
paid: true
input: [videoIds]
output: [retried, failed]
constraints: [只重试失败镜头, 幂等键防重复扣费, 付费前确认]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把没出来的镜头再跑一遍" → video.retry({ scope })
  - 用户："哪几镜没成" → video.listFailed({ projectId })
---

## 说明
### 这个 SKILL 干什么
视频生成按秒计费，重复提交就是重复花钱。这一步只处理没成的：状态是失败、或者提交了
但拿不到任务编号的那几镜，其余一律跳过。

### 具体做四件事
1. 点名：从任务记录里挑出失败与结果不确定的镜头。
2. 先查后提：不确定的先拿任务编号去查一次，能救回来的就不重发。
3. 重跑：按原提示词与原模型重提，幂等键沿用。
4. 报账：重提几镜、救回几镜、仍失败几镜。

### 什么时候用它
- 批量提交跑完，有几镜明显失败。
- 提交结果不确定（没拿到任务编号），先查再决定要不要重发。

### 输入／输出
- 输入：要重试的镜头编号（默认取失败清单）。
- 输出：重试结果（成功、仍失败）。

### 用到的工具
- `video.retry`：10 视频生成 → 重试失败项
- `video.batchSubmit`：10 视频生成 → 提交生成

### 约束与验收
- 先查后提：结果不确定的不许直接重发，重复提交等于重复扣费。
- 重提前把「要花多少秒」说清楚，等用户点头。
- 连续失败三次就停下报因，交给用户决定。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
