---
name: script-structured-generation
displayName: 结构化剧本生成
description: 将已确认的自然语言剧本整理为结构化 Markdown，含角色、场景、道具与分场信息
stage: 剧本结构
capabilities: [long-context, structured-output, creative-writing]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [script_contract.structure_script, script_contract.review_structured_script, script_contract.revise_structured_script, script_contract.write_structured_script]
dependsOn: []
conflictsWith: []
parallelizable: false
paid: false
input: [scriptRaw]
output: [structuredScript]
constraints: [结构化 Markdown 输出, 不修改原稿, 角色一致性, 情绪曲线标注]
feedback:
  - onProgress: 更新三虎进度
  - onComplete: 通知并推进阶段
examples:
  - 用户："将已确认原稿整理为分场剧本" → 读取 writing/script_raw.md 并写入 writing/script.md
---

## 说明
### 这个 SKILL 干什么
把一份已确认的自然语言剧本整理成结构化剧本：场次表、每场的人物、对白、动作与情绪节拍，落成
`writing/script.md`。它属于「剧本结构」阶段，后面拆镜、配音、字幕都读它。

### 具体做四件事
1. 定结构：按分集与场次切分，标出每场的时空、出场人物与戏剧目的。
2. 写对白：口语、可念，带说话人；修饰性的旁白另标，别混进对白里。
3. 写动作与情绪：只写镜头能拍到的东西（动作、表情、走位），不写内心独白。
4. 标节拍：每场给出起承转合与钩子位置，供分镜按时长分配镜头。

### 什么时候用它
- 剧本准备已产出并确认 `writing/script_raw.md` 后，在「剧本结构」阶段执行。
- 已有原稿但要重排结构（拖节奏、补钩子、按集切分）时。

### 输入／输出
- 输入：已确认的 `writing/script_raw.md`。
- 输出：结构化剧本 Markdown（场次表 ＋ 对白 ＋ 动作），可以直接进「初步分镜」。
- 落盘：`writing/script.md`（结构化正稿）；角色／场景／道具三类清单的字段由它定型。
- 拆出来的两步并回这一份：台词那一段由 `script-dialogue-polish` 承担（产物并回正稿，不单独
  出文件），设定那一段由 `script-worldbuilding` 承担（产物落 `docs/world_bible.md`，人读）；
  两步都是本 SKILL 的子步骤——署名与产物归属仍在正稿这一份，不另立产出。

### 用到的工具
- `script_contract.structure_script`：从原稿提取角色、场景、道具与分场内容，生成结构化 Markdown。
- `script_contract.write_structured_script`：原子写入 `writing/script.md`；绝不覆盖 `writing/script_raw.md`。

### 约束与验收
- 一集之内人物称呼一致；同一场不许出现两个时空。
- 对白长度按目标时长控住（默认每集 60～120 秒的量），不写超长的独白。
- 不替用户改设定：人物名、关系、结局以项目里已确认的设定为准。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
