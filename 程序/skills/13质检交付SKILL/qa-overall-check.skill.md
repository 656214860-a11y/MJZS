---
name: qa-overall-check
displayName: 整体质检门禁
description: 对成片做整体质检，覆盖画面、音频、字幕、风格、合规
stage: 质检与交付
capabilities: [vision, reasoning]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [qa.visualCheck, qa.audioCheck, qa.subtitleCheck, qa.styleCheck, qa.complianceCheck]
dependsOn: [edit-auto-compose]
conflictsWith: []
parallelizable: true
paid: false
input: [composedVideo, projectContext]
output: [qaReport, issues]
constraints: [三级门禁 P0/P1/P2, 不合规拦截, 问题可追溯]
feedback:
  - onProgress: 更新三虎进度
  - onError: 严重问题通知用户
  - onComplete: 通知并推进阶段
examples:
  - 用户："做整体质检" → qa.visualCheck() + qa.audioCheck() + ...
---

## 说明
### 这个 SKILL 干什么
交付前的总门槛：把整集的成片、字幕、资产来源与配置统一过一遍，出「能不能交」的结论
与问题清单。它不改任何东西，只放行或拦下。

### 具体查六件事
1. 镜头齐不齐：本集每个未删除的镜头是不是都有通过验收的成片。
2. 技术与一致性：逐镜的技术质检与角色／风格一致性有没有未处理的低分项。
3. 音画：字幕文件与音轨是否齐备、同步报告有没有超阈值项。
4. 资产来源：每一张外部素材是不是都有来源／作者／许可记录。
5. 成本与配置：本集调用的付费接口与模型是否都在记录里、有没有异常中断。
6. 一致性锁定：定稿分镜与成片用的一致基线是不是同一版。

### 什么时候用它
- 质检与交付页点「整体检查」。
- 每次导出交付包之前（导出会先看它的结论）。

### 输入／输出
- 输入：整集的所有阶段结果（镜头、字幕、资产、台账）。
- 输出：通过／不通过 ＋ 按类别的问题清单（每条指到具体镜头或文件）。

### 用到的工具
- `qa.overallCheck`（11 质检与交付 → 整体检查）
- `qa.styleCheck`／`qa.complianceCheck`（风格与合规两项专项）

### 约束与验收
- 有未通过项就不出「通过」结论（不替用户抹平风险）。
- 每条问题都要指到具体对象，能直接照着修。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
