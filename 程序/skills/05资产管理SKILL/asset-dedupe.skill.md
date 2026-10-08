---
name: asset-dedupe
displayName: 资产去重
description: 把同图不同名、同角色多份的候选合并成一份，删前先给清单
stage: 资产管理
capabilities: [vision, structured-output]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [asset.copyrightFilter, asset.retry]
dependsOn: [asset-auto-fill]
conflictsWith: []
parallelizable: true
paid: false
input: [candidates]
output: [unique, duplicates]
constraints: [同图不同名算一份, 保留来源, 删除前给清单]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："查一下资产有没有重复的" → asset.dedupe({ scope })
  - 用户："把重复的合并掉" → asset.mergeDuplicates({ planId })
---

## 说明
### 这个 SKILL 干什么
把重复的候选收成一份：同一张图的多个名字算一份，同一个角色的多轮结果按最像的留一份。
合并是「留下哪一份、其余归到哪儿」的清单，不是直接删文件。

### 具体做四件事
1. 算指纹：按图片内容算一份指纹，同图的先归一堆。
2. 并同角色：同一个角色／场景的多轮结果按相似度排序，留下最像的。
3. 出清单：写明留下哪一份、其余几份为什么归并。
4. 交确认：真要删文件时把清单交给用户点头，删的是入库的那一份之外的副本。

### 什么时候用它
- 同一个角色补了好几轮，资产表里冒出好几份。
- 入库前先清一遍重复，免得后面混着用。

### 输入／输出
- 输入：候选项（可含多轮结果）。
- 输出：去重后的候选、重复项清单（含归并理由）。

### 用到的工具
- `asset.copyrightFilter`：03 资产管理 → 版权过滤（同一张图的不同来源认得出）
- `asset.retry`：03 资产管理 → 重试失败项

### 约束与验收
- 同图不同名算一份：不许因为文件名不同就当成两张。
- 删之前一定先给清单：清单一出来就停，等用户点头。
- 来源、作者与许可随保留的那一份一起留着。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
