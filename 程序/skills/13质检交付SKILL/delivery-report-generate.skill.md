---
name: delivery-report-generate
displayName: 交付报告生成
description: 生成交付报告，含耗时、成本、重试次数、成功率、Token 消耗、缓存命中率
stage: 质检与交付
capabilities: [structured-output]
preferredModels: [deepseek-v4-flash]
fallbackModels: [deepseek-v4-pro]
tools: [delivery.generateReport, delivery.exportManifest, delivery.archive]
dependsOn: [qa-overall-check]
conflictsWith: []
parallelizable: true
paid: false
input: [projectId, allStageResults]
output: [deliveryReport, manifest]
constraints: [报告完整可追溯, 成本/耗时统计准确, 支持导出]
feedback:
  - onProgress: 更新三虎进度
  - onComplete: 三虎通知交付完成
examples:
  - 用户："生成交付报告" → delivery.generateReport()
---

## 说明
### 这个 SKILL 干什么
出交付这一份的东西：交付报告（耗时、成本、重试次数、成功率、Token 消耗、缓存命中率）、
交付清单（manifest）与整包归档。

### 具体做四件事
1. 汇总全过程：每个阶段的耗时与花费、重试与失败、模型调用与命中率。
2. 列交付清单：成片、字幕、封面、资产来源记录各一份，逐个登记路径与校验值。
3. 生成报告：写成可直接交给客户或存档的文档，数字全部来自台账（不估）。
4. 归档：把上面这些打成一个包，放进项目的交付目录。

### 什么时候用它
- 质检与交付页点「导出交付包」。
- 交给合作方或存档之前再出一版最新报告。

### 输入／输出
- 输入：项目、各阶段的运行结果。
- 输出：交付报告、交付清单（manifest）、归档包。

### 用到的工具
- `delivery.generateReport`／`delivery.exportManifest`／`delivery.archive`

### 约束与验收
- 报告里每个数字都要能追到台账或文件，取不到就写「未记录」而不是编一个。
- 清单里的路径与校验值必须与包里的文件一致。
- 不覆盖用户手工改过的报告：新的一版另存。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
