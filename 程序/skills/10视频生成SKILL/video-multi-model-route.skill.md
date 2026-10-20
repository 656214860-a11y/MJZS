---
name: video-multi-model-route
displayName: 多模型路由
description: 按镜头类型与预算把镜头分派给最合适的模型，先算钱再跑
stage: 视频生成
capabilities: [reasoning, structured-output]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [video.batchSubmit, video.pause]
dependsOn: [video-batch-submit]
conflictsWith: []
parallelizable: true
paid: false
input: [shotChain, budget]
output: [routePlan, estimatedCost]
constraints: [按镜头类型选模型, 超预算先问, 不越过 ModelRouter]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："这一集怎么配模型最省" → video.routeModel({ budget })
  - 用户："按这个方案要花多少" → video.simulateCost({ planId })
---

## 说明
### 这个 SKILL 干什么
不是每一镜都值得用最贵的模型：人物特写、复杂运镜与普通过场可以分开派。这一步给出一份
分派方案与预估花费，超预算就先停下来问。

### 具体做四件事
1. 分类：按景别、动作复杂度与人物数量给镜头分档。
2. 配模型：先读取项目 `video_model_version` 与适用的 `reference_mode`，在锁定版本及能力范围内分派并写明依据；其他版本只列为比较建议，不自动切换，也不在本阶段重新弹问模型锁。无总控的独立调试仍按明确选择的模型配置执行。
3. 算钱：按秒数与单价比出预估花费。
4. 对预算：超了就把方案摆出来问用户，不擅自降档。

### 什么时候用它
- 整集镜头多、想省一点成本。
- 用了新模型，想先看看分派之后贵多少。

### 输入／输出
- 输入：镜头链、可用预算。
- 输出：分派方案、预估花费。

### 用到的工具
- `video.batchSubmit`：10 视频生成 → 提交生成
- `video.pause`：10 视频生成 → 暂停（超预算先停下）

### 约束与验收
- 不越过 ModelRouter：模型可用性、成本与限流仍由它核验；自动降级或 fallback 不得覆盖项目已锁定的视频模型版本。必填锁缺失则记录并退回剧本准备／项目配置，不自行默认。
- 超预算要停下来问，不许悄悄换成便宜的模型。
- 方案里要写清每一档的判断依据，方便复盘。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
