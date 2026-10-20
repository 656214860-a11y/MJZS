---
name: storyboard-version-snapshot
displayName: 定稿版本登记
description: 登记这一版定稿；日期后缀区分版本，旧版由回收站退役
stage: 分镜定稿
capabilities: [structured-output]
preferredModels: [deepseek-v4-flash]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.save, storyboard.validate]
dependsOn: [storyboard-final-validate]
conflictsWith: []
parallelizable: true
paid: false
input: [syncedStoryboard]
output: [registeredStoryboard, versionList]
constraints: [只登记已校验分镜, 不覆盖历史版本, 记时间与摘要]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把这一版登记下来" → storyboard.save({ source })
  - 用户："现在用的是哪一版" → 查看定稿日期后缀目录
---

## 说明
### 这个 SKILL 干什么
每定一版就登记一次分镜，记录时间和摘要。定稿目录带日期后缀用来区分版本；需要退役旧版时走回收站，不在程序里另建版本目录。

### 具体做三件事
1. 校验：登记前先过一遍分镜契约校验。
2. 登记：调用 `storyboard.save` 登记当前定稿。
3. 记录：在交付说明里写时间、镜头数和本次变更摘要。

### 什么时候用它
- 定稿完成后登记当前版本。
- 需要说明本次改了哪几镜、用了哪份定稿时。

### 输入／输出
- 输入：对齐并通过校验的分镜 JSON（连同资产清单）。
- 输出：已登记的分镜、版本说明。

### 用到的工具
- `storyboard.save`：登记这份分镜
- `storyboard.validate`：存之前先过一遍契约校验

### 约束与验收
- 只登记已通过校验的分镜，不覆盖旧版文件。
- 版本以定稿目录的日期后缀为准；旧版退役必须走回收站。
- 摘要要写人话（改了哪几镜、加了几个资产），别只写文件指纹。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
