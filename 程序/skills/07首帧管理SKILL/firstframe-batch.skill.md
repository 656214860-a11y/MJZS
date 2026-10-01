---
name: firstframe-batch
displayName: 首帧批量生成
description: 支持全部/指定帧/选中帧生成
stage: 首帧管理
capabilities: []
preferredModels: []
fallbackModels: []
tools: [firstframe.batchGenerate]
dependsOn: [storyboard-prompt-render]
conflictsWith: []
parallelizable: true
paid: true
input: [projectId, scope, frameIds]
output: [submitted, failed]
constraints: [付费步骤批量提交前确认, 生图 200 张/项目]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试
  - onComplete: 通知并推进阶段
examples:
  - 用户："把缺少的首帧都补了" → batchGenerate({ scope: 'missing' })
  - 用户："只生成第3、5、7帧" → batchGenerate([3,5,7])
  - 用户："生成选中的" → 读取 UI 勾选 → batchGenerate(selected)
---

## 说明
### 这个 SKILL 干什么
按分镜的图片提示词批量出首帧（图生视频的起始帧）：支持全部、缺失的、勾选的、指定编号
这几种范围，跑完把结果按镜头号入库。

### 具体做四件事
1. 收范围：全部／只缺的／你在页面上勾的／点名的那几镜。
2. 逐镜取提示词与参考图，按当前生图模型与尺寸出图。
3. 出完按镜头号入库，替换同一镜的旧首帧（旧图按规则进回收站）。
4. 失败的重试并记账；仍失败的在页面上标出来，等你看一眼再决定。

### 什么时候用它
- 首帧管理页点「手动制作首帧」，或勾上「自动补首帧」让它自己补缺口。
- 只补某几镜：先勾选，再点「手动制作首帧」。

### 输入／输出
- 输入：项目、范围（全部／缺失／勾选／指定编号）、目标生图模型与尺寸。
- 输出：已提交（含镜头号）、失败（含原因）。

### 用到的工具
- `firstframe.batchGenerate`（06 首帧管理 → 手动制作首帧）
- 本地 ComfyUI 或线上生图模型接口：在首帧管理页的「连接与模型接口」里选。

### 约束与验收
- 这一步要花钱：批量提交前确认一次，超预算停下。
- 一个项目默认不超过 200 张生图。
- 首帧必须能被视频生成读到：尺寸与格式按所选视频模型的要求出。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
