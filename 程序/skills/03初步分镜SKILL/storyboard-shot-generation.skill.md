---
name: storyboard-shot-generation
displayName: 镜头链生成
description: 将剧本转化为可执行的镜头链，含景别、机位、动作、时长、情绪
stage: 初步分镜
capabilities: [long-context, structured-output, creative-writing]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.generate, storyboard.validate, storyboard.save]
dependsOn: [script-structured-generation]
conflictsWith: []
parallelizable: false
paid: false
input: [structuredScript, characters, style]
output: [shotChain]
constraints: [景别多样性, 镜头时长合理, 情绪节奏匹配, 可拍摄性]
feedback:
  - onProgress: 更新三虎进度
  - onComplete: 通知并推进阶段
examples:
  - 用户："生成初步分镜" → storyboard.generate()
---

## 说明
### 这个 SKILL 干什么
把结构化剧本拆成可执行的镜头链：每镜给景别、机位、动作、时长与情绪，写成 JSON 分镜
（`分镜/<EP>.json`），供首帧、白模与视频生成直接读。

### 具体做五件事
1. 按场次拆分镜头，一镜一个连贯动作，不把两个动作塞进同一镜。
2. 给每镜定景别（远／全／中／近／特）与机位（平／俯／仰、正／侧／背），景别要有变化。
3. 写动作起止（谁从哪儿到哪儿、手上拿着什么），保证前后镜能接上。
4. 分配时长，全场合计对齐本集目标时长；给每镜标情绪与节奏（推进／停顿／爆点）。
5. 生成稳定的镜头编号（SH001、SH002…按剧本顺序，不跳号、不重排）。

### 什么时候用它
- 初步分镜页点「手动制作分镜」。
- 改了剧本某几场之后重跑，把这几场的镜头重排、编号重编。

### 输入／输出
- 输入：结构化剧本、人物与画风设定、每集时长。
- 输出：镜头链 JSON（含编号、景别、机位、动作、时长、情绪、对白归属）。

### 用到的工具
- `storyboard.generate`：生成镜头链。
- `storyboard.validate`：查编号连续性、景别重复、时长合计。
- `storyboard.save`：落盘到项目的分镜目录。

### 约束与验收
- 镜头编号必须按剧本前后顺序生成，不允许乱序（用户报过的「EP003 从 SH017 起」就是这么来的）。
- 同一场里轴线一致：不出现人物突然左右互换。
- 时长合计与目标时长差不超过一成；单镜不超过 8 秒。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
