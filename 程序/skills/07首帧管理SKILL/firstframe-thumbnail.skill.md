---
name: firstframe-thumbnail
displayName: 首帧缩略图
description: 给已导入的首帧生成并缓存缩略图，供页面内容框直接看
stage: 首帧管理
capabilities: []
preferredModels: []
fallbackModels: []
tools: [firstframe.batchGenerate, firstframe.qualityCheck]
dependsOn: [firstframe-batch]
conflictsWith: []
parallelizable: true
paid: false
input: [frameIds, size]
output: [thumbnails]
constraints: [不放大原图, 只支持 PNG 与 GIF, 按图缓存不重复造]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："首帧那一栏直接显示图" → firstframe.makeThumbnail({ frameIds, size })
  - 用户："这块格子怎么还是字" → firstframe.cacheThumbnail({ frameIds })
---

## 说明
### 这个 SKILL 干什么
首帧内容框里那一格要直接看见图，就得有一份小图：按长边不超过指定尺寸抽点缩到目标大小，
按路径与改动时间缓存，第二次看同一张就不再解一遍。

### 具体做四件事
1. 量原图：读 PNG／GIF 文件头拿宽高。
2. 挑倍数：算一个「长边不超过目标」的最大整数倍抽点，不放大。
3. 出小图：交给界面直接摆，同时按路径与时间缓存。
4. 退化处理：格式 Tk 读不出来（jpg／webp）或文件不在，就退回原来的文字，不抛错。

### 什么时候用它
- 首帧管理页与视频生成页把首帧列改成看图的时候自动用。
- 首帧被替换之后要重造小图（改动时间变了，缓存自动失效）。

### 输入／输出
- 输入：镜头编号、目标尺寸。
- 输出：缩略图（按路径缓存）。

### 用到的工具
- `firstframe.batchGenerate`：06 首帧管理 → 手动制作首帧（小图跟着出的那一张走）
- `firstframe.qualityCheck`：读 PNG／GIF 文件头拿宽高，格式不认就退回文字

### 约束与验收
- 不放大原图：比目标还小的图原样用。
- 只认 PNG 与 GIF（Tk 原生那两种），别的格式退回文字。
- 小图只给界面看：不许拿它替换原图或写回分镜。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
