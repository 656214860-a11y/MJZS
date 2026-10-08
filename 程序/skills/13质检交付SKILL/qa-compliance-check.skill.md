---
name: qa-compliance-check
displayName: 合规检查
description: 按平台规范查敏感内容与风险点，结论可追溯且不自动改片
stage: 质检与交付
capabilities: [reasoning, vision]
preferredModels: [gpt-4o, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [qa.complianceCheck, delivery.archive]
dependsOn: [qa-overall-check]
conflictsWith: []
parallelizable: true
paid: false
input: [composedVideo, projectContext]
output: [complianceReport]
constraints: [敏感内容拦截, 结论可追溯到镜与帧, 不自动改片]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："这条能直接上传吗" → qa.complianceCheck({ platform })
  - 用户："有哪些地方可能违规" → qa.reportRisk({ level })
---

## 说明
### 这个 SKILL 干什么
上线前的那一道闸：暴力、惊悚、未成年形象、品牌与真人肖像这几类风险，逐镜看一遍，按
风险等级列出来。只报不改——改片是创作决定。

### 具体做四件事
1. 逐镜看：按风险类别过一遍画面与台词。
2. 定等级：分「拦下／需确认／提示」三级。
3. 写依据：每条写明在哪一镜、第几帧、触犯了哪一条。
4. 出报告：按等级排序，拦下的排最前。

### 什么时候用它
- 交付上传之前的一次总检。
- 换了平台（规范不一样）要重新过一遍。

### 输入／输出
- 输入：成片、项目上下文（题材与目标平台）。
- 输出：合规报告（按风险等级排序）。

### 用到的工具
- `qa.complianceCheck`：11 质检与交付 → 合规检查
- `delivery.archive`：11 质检与交付 → 打包交付

### 约束与验收
- 只报不改：不替用户下架、裁剪或打码。
- 结论要能追溯到镜与帧，方便用户复核。
- 拿不准的按「需确认」报，不许按「没问题」放过。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
