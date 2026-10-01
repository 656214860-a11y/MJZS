---
name: storyboard-consistency-lock
displayName: 一致性锁定
description: 锁定角色外观、场景风格、镜头语言，确保后续生成不漂移
stage: 分镜定稿
capabilities: [vision, reasoning]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.lockConsistency, storyboard.checkDrift]
dependsOn: [storyboard-prompt-render]
conflictsWith: []
parallelizable: false
paid: false
input: [imagePrompts, characterProfiles, style]
output: [lockedAssets, driftReport]
constraints: [角色四视图锁定, 场景概念图锁定, 风格锚点锁定]
feedback:
  - onProgress: 更新三虎进度
  - onError: 发现漂移时通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："锁定角色一致性" → storyboard.lockConsistency()
---

## 说明
### 这个 SKILL 干什么
把定稿分镜里「不能变的东西」锁起来：人物外观、场景样式、画风与关键道具，形成一份一致性
基线，供首帧与视频生成对齐（换镜不换脸）。

### 具体做四件事
1. 读入 03_continuity/output/continuity_ledger.json（连贯性清单产出的冻结锚点与冲突裁决）。
2. 把每个出场人物在本集的锚点锁进定稿分镜（锚点字符串逐字复用，不改写）。
3. 把场景的固定要素（光源方向、空间锚点）锁进相关镜头的 continuity_flags。
4. 给每镜标出它引用到的角色与场景编号，并核对三元组一致。

### 什么时候用它
- 分镜定稿、准备出首帧之前。
- 中途发现「同一角色两张脸」时，重新锁一次并回填引用编号。

### 输入／输出
- 输入：定稿分镜、资产表、03_continuity/output/continuity_ledger.json。
- 输出：锁进分镜的锚点与引用清单（连续性约束本身由连贯性清单生成，这里不再重写一遍）。

### 用到的工具
- `storyboard.lockConsistency`：生成基线。
- `storyboard.attachReferences`：把基线编号回填到每镜。

### 约束与验收
- 基线只写「看得见」的项，不写性格与剧情。
- 没在资产表里出现过的人物不许凭空补外观，先报缺。
- 第 61 期 v0.8 任务 6：外观抽点与连续性约束生成都已归口别处，这里只锁不改。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
