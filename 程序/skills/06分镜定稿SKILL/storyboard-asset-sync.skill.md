---
name: storyboard-asset-sync
displayName: 分镜与资产同步
description: 把分镜里引用的资产与资产表对齐，缺的列成清单
stage: 分镜定稿
capabilities: [structured-output]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.checkDrift, storyboard.lockConsistency]
dependsOn: [storyboard-prompt-render, asset-auto-fill]
conflictsWith: []
parallelizable: true
paid: false
input: [shotChain, assets]
output: [syncedStoryboard, missingAssets]
constraints: [资产引用可解析, 缺项列清单, 不改分镜内容]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把分镜和资产对一遍" → storyboard.syncAssets({ source })
  - 用户："还缺哪些资产" → storyboard.checkMissingAssets({ source })
---

## 说明
### 这个 SKILL 干什么
分镜里写着「CHAR_001」，资产表里得有这一项、还得有图——这一步就是把两边的名字对齐，
对不上的列成一份缺项清单交给你。

### 具体做四件事
1. 读引用：把镜头里引用的角色、场景与道具都抽出来。
2. 对名字：与资产表逐项核对，编号与名称不一致的（改名、合并）当场对上。
3. 查有没有图：对上的项目还要看资产图在不在。
4. 出清单：缺的、断链的分条列出，附上它出现在哪几镜。

### 什么时候用它
- 定稿之前先确认资产齐了。
- 资产表改过名或合并过之后，回头把分镜里的引用对一遍。

### 输入／输出
- 输入：镜头链、资产表。
- 输出：对齐后的分镜、缺项清单（含出现在哪几镜）。

### 用到的工具
- `storyboard.checkDrift`：05 分镜定稿 → 检查漂移（分镜与资产表谁变了）
- `storyboard.lockConsistency`：05 分镜定稿 → 一致性锁定

### 约束与验收
- 只对齐不改内容：镜头内容与提示词一个字不动。
- 缺项不许悄悄补一个占位资产，一律列出来等确认。
- 改名与合并要留下对照，方便回退。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
