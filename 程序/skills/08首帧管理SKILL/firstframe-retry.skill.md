---
name: firstframe-retry
displayName: 失败首帧重试
description: 只把生成失败的首帧重跑一遍，成功的绝不重复提交
stage: 首帧管理
capabilities: [structured-output]
preferredModels: [deepseek-v4-flash]
fallbackModels: [deepseek-v4-pro]
tools: [firstframe.retry, firstframe.batchGenerate]
dependsOn: [firstframe-batch]
conflictsWith: []
parallelizable: true
paid: true
input: [frameIds]
output: [retried, failed]
constraints: [只重试失败的, 不重复提交成功的, 付费前确认]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把没生成出来的首帧再跑一遍" → firstframe.retry({ scope })
  - 用户："哪几镜首帧没成" → firstframe.listFailed({ projectId })
---

## 说明
### 这个 SKILL 干什么
首帧批量生成跑完之后总会有几镜没成：网络抖、被拦、超时。这一步只把这几个重跑，跑成功
的那些一个都不碰——不重复扣钱。

### 具体做四件事
1. 点名：从任务记录里挑出失败与不确定的镜头。
2. 去重：已经在跑的、已经就绪的一律跳过。
3. 重跑：按原提示词与原模型重提一次，幂等键沿用。
4. 报账：成功几个、还差几个，逐镜写清楚。

### 什么时候用它
- 批量生成跑完，状态里有几镜是失败。
- 隔了一天回来，先把没成的补上。

### 输入／输出
- 输入：要重试的镜头编号（默认取失败清单）。
- 输出：重试结果（成功、仍失败）。

### 用到的工具
- `firstframe.retry`：06 首帧管理 → 重试失败项
- `firstframe.batchGenerate`：06 首帧管理 → 手动制作首帧

### 约束与验收
- 成功的绝不重提：重复提交等于重复扣费。
- 重试前把「要花几张图」说清楚，等用户点头。
- 同一个镜头连续失败三次就停下来报因，别再自动重试。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
