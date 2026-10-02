---
name: asset-copyright-filter
displayName: 版权过滤与来源记录
description: 过滤版权不明或受限的候选图，记录来源、作者、许可
stage: 资产管理
capabilities: []
preferredModels: []
fallbackModels: []
tools: [asset.copyrightFilter]
dependsOn: [asset-auto-fill]
conflictsWith: []
parallelizable: true
paid: false
input: [candidates]
output: [filtered]
constraints: [CC0/CC-BY 优先, 版权不明默认拦截, 记录来源/作者/许可]
feedback:
  - onProgress: 更新三虎进度
  - onError: 版权异常通知用户
  - onComplete: 通知并推进阶段
examples:
  - 输入候选图 → asset.copyrightFilter({ candidates, allowCC0: true, allowCCBY: true })
---

## 说明
### 这个 SKILL 干什么
把候选素材里版权不明或受限的挑出去，只放行可商用／可署名的那些，并把来源、
作者、许可记进资产台账——交付时这一份就是授权链路的凭据。

### 具体做四件事
1. 逐个候选读授权信息：许可类型、是否允许商用、是否要求署名、是否允许改动。
2. 按白名单放行（默认 CC0 与 CC-BY），版权不明的一律拦下并写明原因。
3. 把放行的候选连同来源链接、作者、许可写进台账，供交付报告引用。
4. 拦截项也留一份清单，方便你回头找替代素材。

### 什么时候用它
- 资产搜索之后、入库之前。
- 交付前对整本资产台账复查一遍，确认来源齐全。

### 输入／输出
- 输入：候选素材（含各自来源信息）。
- 输出：放行清单（含来源／作者／许可）与拦截清单（含原因）。

### 用到的工具
- `asset.copyrightFilter`（资产入库前的过滤）

### 约束与验收
- 宁可误拦，不可错放：拿不准授权的一律拦下。
- 缺失授权信息的不能靠默认值放行。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
