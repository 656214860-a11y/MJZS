---
name: asset-auto-fill
displayName: 缺图自动补齐
description: 复用现有自动补资产执行器，走增强+调度+反馈
stage: 资产管理
capabilities: [vision]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [asset.startAutoFill, asset.retry, asset.pause, asset.resume, asset.importAssets]
dependsOn: [asset-search, asset-rank, asset-dedupe, asset-copyright-filter, asset-candidate-wall]
conflictsWith: []
parallelizable: true
paid: false
input: [projectId, scope, assetType]
output: [added, filtered, failed]
constraints: [复用现有执行器, 不重写搜索/入库, 默认半自动候选墙确认]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："给林月补参考图" → asset.startAutoFill({ scope: 'character:林月' })
  - 用户："补全所有缺失场景" → asset.startAutoFill({ scope: 'missing:scene' })
---

## 说明
### 这个 SKILL 干什么
补资产这一步的「无人值守」档：按缺口自动跑一轮「搜索 → 排序 → 去重 → 版权过滤 → 候选墙」，
把缺参考图的人物与场景补齐，或生成可直接用的资产图。

### 具体做五步
1. 算出缺口：资产表里还没有可用参考图（或已失效）的条目。
2. 按条目类型决定做法：写实素材走搜索，原创形象走生图。
3. 检索或生图，拿到候选（搜索走本地ComfyUI或线上接口，取决于页面上选的生图模型）。
4. 版权过滤 ＋ 去重 ＋ 相似度排序，留下最像的几条。
5. 半自动档只铺候选墙等你点头；全自动档按阈值直接入库并记来源。

### 什么时候用它
- 资产管理页勾上「自动补资产」后，这一步就按缺口自动跑一轮（第 64 期任务 11：这份 SKILL 原来
  叫「无人值守自动补资产」，与页面上那个开关同名，用户以为是两个开关；它只是这一步的 SKILL，
  真正的无人值守开关只有一个——资产页的「自动补资产」勾选框）。
- 中途加了新人物／新场景，重新补一轮缺口。

### 输入／输出
- 输入：项目、补哪些（缺口／指定角色场景）、资产类型。
- 输出：新增（入库）、被过滤掉（含原因）、失败（可重试）。

### 用到的工具
- `asset.startAutoFill`（03 资产管理 → 自动补资产）
- `asset.retry`／`asset.pause`／`asset.resume`（重试失败项／暂停／继续）
- `asset.importAssets`（导入候选）

### 约束与验收
- 复用现有执行器，不另写一套搜索与入库。
- 版权不明的默认拦下；来源、作者、许可随图入库。
- 生成类资产要花钱：全自动档也只在预算内跑，超预算停下来问你。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
