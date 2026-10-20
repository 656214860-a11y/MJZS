---
name: video-batch-submit
displayName: 视频批量提交
description: 批量提交图生视频/文生视频，轮询状态，失败重试
stage: 视频生成
capabilities: []
preferredModels: []
fallbackModels: []
tools: [video.batchSubmit, video.pollStatus, video.retry, video.pause, video.resume]
dependsOn: [firstframe-quality, whitemodel-motion-preview]
conflictsWith: []
parallelizable: true
paid: true
input: [projectId, videoIds, mode]
output: [submitted, completed, failed]
constraints: [付费步骤批量提交前确认, 视频 100 镜/项目, 幂等键]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："生成所有视频" → video.batchSubmit({ scope: 'all' })
  - 用户："只生成第5、8镜" → video.batchSubmit([5,8])
---

## 说明
### 这个 SKILL 干什么
把首帧（图生视频）或提示词（文生视频）批量交给视频模型，轮询进度、下载成片、失败重试，
并把每个镜头的结果按编号入库。

### 具体做五步
1. 收范围：全部已就绪的镜头／你勾选的镜头。
2. 组装参数：首帧或提示词、分辨率、时长、是否带声音，按所选模型的能力来。
3. 逐个提交（带幂等键，网络抖动不重复下单），拿到任务号。
4. 轮询状态，成功后下载成片落盘；失败按可重试／不可重试分档处理。
5. 汇总：已提交、已完成、失败（含原因），并推进到质检。

### 什么时候用它
- 视频生成页点「手动制作视频」（线上／本地两种生成方式都走它）。
- 已按需求规模调好预算后，勾上「自动提交（不超预算）」让它自己跑。

### 输入／输出
- 输入：项目、镜头范围、生成方式（线上 API／本地 ComfyUI）、分辨率与时长。
- 输出：已提交、已完成（含文件路径）、失败（含原因）。

### 用到的工具
- `video.batchSubmit`（10 视频生成 → 手动制作视频／批量生成勾选镜头）
- `video.pollStatus`（查任务，页面上的「刷新」也走它）
- `video.retry`／`video.pause`／`video.resume`（重试失败项／暂停／继续）

### 约束与验收
- 这一步要花钱：批量提交前确认一次；「自动提交」也只在不超剩余预算时动手。
- 一个项目默认不超过 100 个镜头；同一镜头不并发重复提交。
- 成片质量交给 video-quality-check（时长、音轨、分辨率）；这一颗只管提交、轮询与重试。
  （第 61 期 v0.8 任务 6：技术质检与视频提示词的静态外观描述都从这里删掉。）

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
