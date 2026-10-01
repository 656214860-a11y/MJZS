---
name: delivery-archive
displayName: 交付归档
description: 把成片、字幕、清单与报告打成一个交付包，只打包不删源
stage: 质检与交付
capabilities: [structured-output]
preferredModels: [deepseek-v4-flash]
fallbackModels: [deepseek-v4-pro]
tools: [delivery.archive, delivery.exportManifest]
dependsOn: [delivery-report-generate]
conflictsWith: []
parallelizable: true
paid: false
input: [projectId, allStageResults]
output: [archive, manifest]
constraints: [只打包不删源, 清单可校验, 路径可追溯]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："打一个交付包" → delivery.archive({ projectId })
  - 用户："给一份带校验的清单" → delivery.exportManifest({ projectId })
---

## 说明
### 这个 SKILL 干什么
收尾那一步：把成片、字幕、资产清单、各阶段的报告与成本统计收成一个交付包，附一份可
校验的清单。项目里的原始文件一个都不删。

### 具体做四件事
1. 收件：按交付清单把成片、字幕、清单与报告挑出来。
2. 算校验：每个文件算一份哈希写进清单。
3. 打包：按固定目录结构压成一个交付包。
4. 留源：项目目录里的原始文件原样留着。

### 什么时候用它
- 片子过审、要交出去或存档的时候。
- 要给别人接手，需要一份能校验的清单。

### 输入／输出
- 输入：项目、各阶段的结果与报告。
- 输出：交付包、校验清单。

### 用到的工具
- `delivery.archive`：11 质检与交付 → 打包交付
- `delivery.exportManifest`：写出交付清单 manifest.json

### 约束与验收
- 只打包不删源：源文件与历史版本一律不动。
- 清单要能校验：哈希与相对路径一个不少。
- 缺件要报：清单里点到的文件不在了就停下来说清楚。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
