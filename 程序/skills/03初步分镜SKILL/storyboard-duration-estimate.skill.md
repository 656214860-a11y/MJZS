---
name: storyboard-duration-estimate
displayName: 时长预估
description: 按对白长度与动作量预估每镜时长，并核对整集总时长
stage: 初步分镜
capabilities: [reasoning, structured-output]
preferredModels: [deepseek-v4-flash]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.pacingCheck, storyboard.validate]
dependsOn: [storyboard-shot-generation]
conflictsWith: []
parallelizable: true
paid: false
input: [shotChain, targetSeconds]
output: [durationPlan, totalSeconds]
constraints: [单镜 2–15 秒, 总时长贴合目标, 对白念得完]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："给每镜配一下时长" → storyboard.estimateDuration({ episodeId })
  - 用户："这一集一共多少秒" → storyboard.checkTotal({ episodeId })
---

## 说明
### 这个 SKILL 干什么
算清楚每一镜该给几秒：对白按字数折算，动作按节拍折算，取大的那个，再卡进平台允许的
2～15 秒。加总后与目标时长对账，差得多的先报出来。

### 具体做四件事
1. 折对白：按每字 0.18～0.25 秒估这句要念多久。
2. 折动作：按起手、过程、收尾估节拍。
3. 取大值：对白与动作谁长按谁算，再卡进 2～15 秒。
4. 对总账：与目标时长比，超出或不足一成五就报出来并给取舍建议。

### 什么时候用它
- 分镜刚生成，要给每镜写上时长。
- 整集超时（超平台限制）或明显偏短时要重新配时长。

### 输入／输出
- 输入：镜头链、整集目标时长。
- 输出：每镜时长方案、整集总时长。

### 用到的工具
- `storyboard.pacingCheck`：按分镜现有的时长算节奏与重复度
- `storyboard.validate`：镜头链契约校验：逐镜时长与总时长一起过

### 约束与验收
- 单镜不许超出 2～15 秒：越界的当场钳住并说明。
- 对白念不完就是错：宁可加时长也不许删词。
- 估出来的数是给用户看的草稿，必须写明是「预估」。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
