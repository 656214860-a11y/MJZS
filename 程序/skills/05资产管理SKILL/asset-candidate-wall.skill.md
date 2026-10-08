---
name: asset-candidate-wall
displayName: 候选墙确认
description: 把排好序的候选铺成一墙，等你点头才入库（半自动默认档）
stage: 资产管理
capabilities: [vision]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [asset.importAssets, asset.startAutoFill]
dependsOn: [asset-visual-rank]
conflictsWith: []
parallelizable: false
paid: false
input: [ranked]
output: [selected]
constraints: [半自动默认, 一次最多九张, 点头才入库]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把候选铺出来我挑一张" → asset.showCandidateWall({ assetId })
  - 用户："就用第三张" → asset.pickCandidate({ assetId, index })
---

## 说明
### 这个 SKILL 干什么
把排好序的候选铺成一面候选墙：一眼看全、点一张就用它。默认这一档是半自动——三虎铺墙
不替你做主，你不点它就不入库。

### 具体做四件事
1. 铺墙：按排序一次摆最多九张，标上分数与来源。
2. 等你点：你选哪张就用哪张；没选就停在这儿。
3. 记来源：入库时把作者、许可与链接一起写进资产记录。
4. 留退路：没被选中的候选保留在候选目录里，不删。

### 什么时候用它
- 自动补资产跑完，要人工过一眼再入库。
- 同一个角色想换一张更像的参考图。

### 输入／输出
- 输入：排好序的候选。
- 输出：你选中的那一份（连同来源记录）。

### 用到的工具
- `asset.importAssets`：03 资产管理 → 导入资产
- `asset.startAutoFill`：03 资产管理 → 自动补资产

### 约束与验收
- 半自动档不许替用户选：没点就什么都不做。
- 一次最多九张：再多就分页，别把墙铺成一片。
- 版权不明的候选根本不上墙（上游版权过滤已经拦过一道）。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
