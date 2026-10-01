---
name: asset-visual-rank
displayName: 视觉相似度排序
description: 按设定文本与参考图给候选资产打分排序，最像的排前面
stage: 资产管理
capabilities: [vision]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [asset.startAutoFill, asset.pause]
dependsOn: [asset-auto-fill]
conflictsWith: []
parallelizable: true
paid: false
input: [candidates, reference]
output: [ranked]
constraints: [按相似度排序, 给出分数与理由, 不改图不改设定]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把候选按像不像排序" → asset.rankBySimilarity({ scope })
  - 用户："哪张最像林月" → asset.scoreCandidates({ assetId })
---

## 说明
### 这个 SKILL 干什么
候选图一堆的时候，按「像不像设定里那个人／那个地方」排序：每张给一个分数与一句理由，
候选墙与半自动入库都按这个次序摆。

### 具体做四件事
1. 读设定：把人物／场景的外观要求读成几条可比对的要点。
2. 逐图打分：按要点给 0～100 的分，并写一句为什么。
3. 排序：分数从高到低，同分的把「更像正面全脸」的排前面。
4. 出清单：给出排序结果与分数，原来的图一张不动。

### 什么时候用它
- 候选墙里挑花眼了，要先有一份次序。
- 自动补资产跑完，想知道哪几张最接近设定。

### 输入／输出
- 输入：候选项（图或链接）、设定的外观要点。
- 输出：排序结果（含分数与理由）。

### 用到的工具
- `asset.startAutoFill`：03 资产管理 → 自动补资产
- `asset.pause`：03 资产管理 → 暂停自动补资产（打分要停下就停）

### 约束与验收
- 只排序不改图：不裁剪、不调色、不改设定。
- 分数要给得出来由：写不出理由的分数按 0 处理。
- 拿不准的候选留在表里，不许直接删。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
