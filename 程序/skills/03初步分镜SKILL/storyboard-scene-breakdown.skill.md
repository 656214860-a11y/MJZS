---
name: storyboard-scene-breakdown
displayName: 场次拆分
description: 把剧本按场次拆成可派工的镜头任务清单，检查有没有漏场与漏信息
stage: 初步分镜
capabilities: [structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.generate, storyboard.continuityCheck]
dependsOn: [script-structured-generation]
conflictsWith: []
parallelizable: true
paid: false
input: [structuredScript]
output: [sceneBreakdown]
constraints: [场次不遗漏, 时空标注清楚, 与剧本场号一致]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："按场次列一张派工单" → storyboard.breakdownScenes({ episodeId })
  - 用户："剧本的场次都拆到了吗" → storyboard.checkCoverage({ episodeId })
---

## 说明
### 这个 SKILL 干什么
拆分镜之前的派工单：一集有哪几场、每场在什么时候什么地方、有谁、要交代什么，逐场
列清楚，并回头核对剧本里的场次有没有漏。

### 具体做四件事
1. 读场次：按剧本的场号逐场登记时空、出场人物与戏剧任务。
2. 标边界：写清每场的进门与出门（上一场接什么、下一场接什么）。
3. 查覆盖：把剧本里的场号与清单对一遍，漏的、多的都报出来。
4. 出清单：落成可派工的场次清单，下一步按它生镜头链。

### 什么时候用它
- 刚开始拆分镜，先要一张干净的场次表。
- 改了剧本场次之后，回头核对分镜有没有跟着漏一场。

### 输入／输出
- 输入：结构化剧本。
- 输出：场次清单（时空、人物、戏剧任务、进出场边界）。
- 落盘：`03初步分镜/output/scene_breakdown.json`（采用分镜时程序按已采用分镜同步写入并核验；每场一条，编号 SC_###，场号与剧本一致）。

### 用到的工具
- `storyboard.generate`：03 初步分镜 → 分镜创作
- `storyboard.continuityCheck`：03 初步分镜 → 连续性检查

### 约束与验收
- 场号与剧本一致：不许自己重新编号。
- 漏场是硬错：报出来先停下问人，不许自己补一场。
- 时空不明的写「待确认」，别猜。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
