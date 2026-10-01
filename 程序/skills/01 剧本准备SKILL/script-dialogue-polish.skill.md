---
name: script-dialogue-polish
displayName: 台词润色
description: 把剧本对白改成口语、可念、有节奏的台词，并给出逐条改动说明
stage: 剧本准备
capabilities: [creative-writing, structured-output]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [script.generate, script.validate]
dependsOn: [script-structured-generation]
conflictsWith: []
parallelizable: true
paid: false
input: [structuredScript, tone]
output: [polishedScript, changeLog]
constraints: [保留剧情与信息量, 口语可念不绕口, 不新增人物与设定]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把这一集的台词念顺一点" → script.polishDialogue({ scope })
  - 用户："这场对白太长了，压到二十秒" → script.polishDialogue({ maxSeconds })
---

## 说明
### 这个 SKILL 干什么
对白这一层的定稿工序：把剧本里的台词逐句读一遍，改成演员张得开嘴、观众一遍听得懂的
口语，同时把每处改动记成一份清单。剧情、人物关系与信息量一条都不动。

### 具体做四件事
1. 逐句过一遍：把书面语、长定语句与重复称呼标出来。
2. 改口语：短句为主，一句一个意思；拗口的词换成日常说法。
3. 调节奏：同一场里长短句交替，别让每句都一样长。
4. 记改动：每条改动写「原句 → 新句 ＋ 为什么」，方便你逐条回退。

### 什么时候用它
- 剧本准备页跑完「结构化剧本生成」之后，想再顺一遍台词。
- 配音前台词念不顺、时长超出预算时要压缩对白。

### 输入／输出
- 输入：结构化剧本、台词基调（方言／古装／现代口语）。
- 输出：润色后的剧本、逐条改动清单。
- 落盘：润色结果并回正稿（结构化剧本），不单独出文件——本步是
  script-structured-generation 的「台词那一段」的子步骤。

### 用到的工具
- `script.generate`：01 剧本准备 → 剧本创作（改完的台词写回剧本）
- `script.validate`：剧本契约校验：改完仍要过字段校验

### 约束与验收
- 剧情、人物名、关系与结局以项目里已确认的设定为准，一律不改。
- 不许为了顺口加信息或删信息：只换说法，不换内容。
- 改动清单要能对着原句看：每一处都能单独回退。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
