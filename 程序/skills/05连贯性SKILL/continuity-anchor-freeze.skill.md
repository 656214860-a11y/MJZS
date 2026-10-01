---
name: continuity-anchor-freeze
displayName: 冻结锚点
description: 按批次冻结必须逐字保住的东西：角色锚点、场景光源与空间锚点、道具尺度
stage: 连贯性清单
capabilities: [structured-output, reasoning]
preferredModels: [qwen-max, deepseek-v4-pro]
fallbackModels: [deepseek-v4-flash]
tools: [continuity.freezeAnchors]
dependsOn: [continuity-conflict-adjudicate]
conflictsWith: []
parallelizable: false
paid: false
input: [assets, shotBatches, costumeId]
output: [frozenAnchors]
constraints: [锚点逐字复用不许改写, 按批次分组, 没在资产表里出现过的不许凭空补]
feedback:
  - onProgress: 更新三虎进度
  - onError: 发现冲突或漂移时通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："把这一批该冻的东西列出来" → continuity.freezeAnchors()
---

### 这个 SKILL 干什么
给每个批次列一份「不许变」的清单：出场角色的锚点（带服装状态覆盖）、场景的光源方向与空间锚点、
道具的材质与尺度。清单落进 continuity_ledger.json 的 batches[].frozen_anchors，同时同步到
_shared/anchors 锚点库。

### 具体做三件事
1. 读当前分镜每镜的 character_ids／scene_id／props 与 costume_id。
2. 从资产清单里取对应锚点，能逐字复用的一字不改；缺锚点的按「先报缺」处理，不编造。
3. 按批次去重，同一批里同一个锚点只出现一次。

### 什么时候用它
- 批次划分（分镜定稿的 shot_batches）之后，首帧生成之前。

### 输入／输出
- 输入：资产清单、分镜的批次划分、每镜的 costume_id。
- 输出：frozen_anchors（kind／id／anchor／state）。

### 用到的工具
- `continuity.freezeAnchors`：对着「04 连贯性清单」页面上的「手动生成连贯性清单」执行。

### 约束与验收
- 锚点是给机器逐字复用的一份字符串，不是给人看图的话术：只写看得见的项。
- 不许把自然语言外观描述重新写一遍（那是 02_assets/docs/character_brief.md 的活）。

## 说明

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与页面上的「手动生成连贯性清单」结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
