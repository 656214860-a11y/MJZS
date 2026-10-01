---
name: script-worldbuilding
displayName: 世界观设定整理
description: 把散落的设定收成一本世界观设定集，并检查与已确认设定是否冲突
stage: 剧本结构
capabilities: [long-context, structured-output]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [script.extractScenes, script.extractProps]
dependsOn: [script-structured-generation]
conflictsWith: []
parallelizable: true
paid: false
input: [structuredScript, notes]
output: [worldBible, rules]
constraints: [设定可追溯, 不与已确认设定冲突, 术语统一]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把设定整理成一本" → script.collectWorldbuilding({ episodeId })
  - 用户："设定有没有前后打架" → script.checkConsistency({ episodeId })
---

## 说明
### 这个 SKILL 干什么
把剧本、备注与随手记里的设定收成一本《世界观设定集》：时间、地点、规则、势力与
专有名词各归一处，顺带把互相打架的地方挑出来。

### 具体做四件事
1. 收集：从剧本与备注里摘出时间、地点、规则、势力、专有名词。
2. 归类：按「世界规则／地理／势力／名词表」分栏，同名同义合并。
3. 查冲突：同一件事两处说法不一致的列出来，并指明出处在哪。
4. 出设定集：落成一份世界观设定，供分镜与资产引用。

### 什么时候用它
- 剧本里设定散在各场，拆分镜时对不上。
- 新增集数或新人物，要先确认不撞已有设定。

### 输入／输出
- 输入：结构化剧本、你的备注与补充说明。
- 输出：世界观设定集、规则清单（含冲突项与出处）。
- 落盘：docs/world_bible.md（人读），不占 output 的 JSON——本步是
  script-structured-generation 的「设定那一段」的子步骤。

### 用到的工具
- `script.extractScenes`：03 资产管理 → 从剧本提取角色／场景／道具（场景那一路）
- `script.extractProps`：同上（道具那一路）

### 约束与验收
- 只收不改：拿不准的写成「待确认」，不替用户定设定。
- 每条设定都要能追溯到出处（哪一场、哪一句）。
- 专有名词统一一份写法，别一会儿「灵气」一会儿「灵力」。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
