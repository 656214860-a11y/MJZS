---
name: storyboard-version-snapshot
displayName: 版本快照
description: 给这一版定稿拍个快照，可回滚可对比
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
output: [snapshot, versionList]
constraints: [只加不改, 可回滚, 记时间与摘要]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："给这一版留个底" → storyboard.snapshotVersion({ source })
  - 用户："上次那版跟现在差在哪" → storyboard.listVersions({ source })
---

## 说明
### 这个 SKILL 干什么
每定一版就拍一张快照：分镜 JSON 与资产清单一起存进版本目录，附时间、摘要与指纹。
后面想回到哪一版，照清单挑。

### 具体做四件事
1. 算指纹：对分镜与资产清单各算一个指纹。
2. 存快照：整份复制进分镜历史下的时间戳目录。
3. 写摘要：记时间、镜头数、与上一版的差别摘要。
4. 列版本：维护一份版本清单，最新的排最前。

### 什么时候用它
- 定稿采用之前，先给当前这版留一张。
- 想比较两版之间改了哪几镜。

### 输入／输出
- 输入：对齐并通过校验的分镜 JSON（连同资产清单）。
- 输出：快照目录、版本清单。

### 用到的工具
- `storyboard.save`：05 分镜定稿 → 保存分镜
- `storyboard.validate`：存之前先过一遍契约校验

### 约束与验收
- 只加不改：快照目录里的旧版本一个都不动。
- 回滚要问过用户：这一步只负责拍快照与列清单。
- 摘要要写人话（改了哪几镜、加了几个资产），别只写文件指纹。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
