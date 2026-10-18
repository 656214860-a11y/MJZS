# R1695 功能轮（源码轮）：剧本准备不再只交付叙事正文——吸收决策引擎的节拍工作流，每集自然剧本带「本集节拍表」

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（源码轮 + SKILL 文档）。按 §2.7 先改 `docs/`（REQ-S01-16／17、DES-S01-16），再改 SKILL 与阶段契约文字，最后补测试。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟通过（0 失败）；受影响冒烟（`workflow_settings workflow_tasks`）通过；架构门禁 **368/368**（OK，未增减）；`tests/test_workflow_writing_stages.py` 全绿（新增 1 条锚定 REQ-S01-16/17，期望链接集合同步扩了 2 项）。`run_selftests -k test_idea_chat test_workflow test_core …` 里有 **9 条红，与本轮无关**，见 D。
3. **project_status.md 的欠账少了吗？** 没有减少；本轮改源码与阶段契约，源码轮全量欠账 +1（按 R1694 记录的 1/8 推算为 2/8），未命中 §5 的升级条件，本轮未跑全量。

## A 为什么做这一轮

用户反馈：剧本准备阶段只输出自然剧本，看不到节拍／权重／雷区；要求取消「只能输出自然剧本」的限制，让 01 吸收 `AIGC创作全流程` 里与剧本输出有关的 SKILL（决策引擎、剧本引擎等），分镜与结构相关的留给 02／03。

「限制」不止在 SKILL 里：`workflow_settings._STAGE_OUTPUT_CONTRACTS['writing']`、`workflow_tasks` 两处任务提示都写着「唯一正式交付物是完整自然语言剧本正文」，模型会被这些最高优先级契约压回纯叙事。

## B 用户裁决（本轮唯一一次提问）

决策引擎的「权重／雷区」其实是镜头选型概念（情境 ID E01~E15、80/15/5 核心组合、构图雷区 A/B）。用户选了 **「只吸收剧本层，权重雷区留给 03」**：
- 01 只取步骤 2「切分节拍」与情绪锚点表前三列；
- 情境 ID、核心组合、构图雷区不进 01，留给 03／07。

## C 改动

- **docs**：`REQUIREMENTS.md` 新增 REQ-S01-16（每集带节拍表，列与铁律）、REQ-S01-17（镜头层不进本阶段）；`DESIGN.md` 新增 DES-S01-16（节拍表定义唯一在 SKILL 模板，契约文字只写一句，不复制列定义）。
- **SKILL**（`skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md`）：
  - ④自然剧本模板加「本集节拍表」（场次／节拍＃／情绪关键词／服务的剧本动作／权重／强度）；
  - 新增「节拍表」小节：每场 3–5 个节拍、关键词具体、权重（主／辅／峰值，每场至多 1 个峰值，**剧本层戏份权重，不是镜头比例**）、强度 0–10 与 `emotion_curve.json` 同刻度、相邻节拍须有变化、不写镜头层内容、分集衔接（首场 10 秒、具体钩子）；
  - 引用新增 `sd-script-engine/SKILL.md#长剧批次合同`（与原链接同一文件，不增 token）与 `references/dialogue-naturalization.md`（台词拟人化，演员角色自检修订，不向正文追加过站卡）；决策引擎引用补一句说明只取哪几步。
- **阶段契约**：`workflow_settings._STAGE_OUTPUT_CONTRACTS['writing']`、`workflow_tasks.script_prompt` 与 `script_followup` 各加同一句「每集在正文前附本集节拍表…不含机位、情境 ID 等镜头层内容」。既有措辞（唯一正式交付物、唯一来源、待确认、不进入 02）**一字未动**。
- **产物边界**：节拍表与正文在同一份自然剧本文件内，不新增文件；`script_contract`、`script_manifest_schema.PRODUCERS`、02 的输入口径均未改。

## D 验证

| 项 | 结果 |
| --- | --- |
| 默认冒烟 | 通过（0 失败） |
| 受影响冒烟 `--affected workflow_settings workflow_tasks` | 通过 |
| 架构门禁 | **368/368** |
| `test_workflow_writing_stages` | 全绿；新增 `test_req_s01_16_17_…`（SKILL 模板列、铁律短语、三处契约含同一句） |
| API 内联预算 | 内联总量 49,271 → 59,857 字符（+约 1.1 万，来自台词拟人化），远低于 300,000 硬上限 |
| 无关红灯 | `test_idea_chat`（SavingTests／SendMessageTests 共 7 条）与 `test_workflow.DesktopModelPoolTests`（2 条）在 **本轮改动 stash 之前同样失败**（同一 9 条，含 `KeyError: 'receipt'`、模型路由期望 Qwen 实得 Codex）。判断为本机环境／模型池状态所致，非本轮引入；未处理，留待后续核查 |

### 断言未动

没有改动、弱化或删除任何既有断言。`test_workflow_writing_stages` 里「链接集合必须等于原引用＋新增引擎」的期望集合新增 2 项（长剧批次合同、台词拟人化），这是链接契约的有意扩展，断言形式不变。

## E 留给用户的事项

1. **权重在剧本层的定义是我的改写**：原包 80/15/5 是镜头组合比例；01 里的「主／辅／峰值」是戏份权重。如不认可可以改成别的口径。
2. **雷区本轮没有出**：按裁决留给 03／07。但 03（`pipeline-storyboard-draft`）和 07 目前**还没接**决策引擎，节拍表后三列（情境 ID／核心组合／雷区）暂时没有人续写——这是待办（见记忆 `sd-decision-engine-injection-todo`），需要另开一轮。
3. **未吸收 `external-script-polish.md`**：它是把外部成型剧本补表演层以适配分镜的规程，更偏 02／03；且因引用整文件内联会多出约 3.5K 字符，故没加。
4. **`emotion_curve.json`（整集 12 节拍）与节拍表（每场 3–5 节拍）粒度不同，并存**；峰值强度两处刻度一致，但程序不做交叉校验。
5. 真机尚未用新 SKILL 跑一次完整④生成，节拍表的实际产出质量需要用户在应用里复验。

## F 提交

已提交（见 git log 中 `R1695:`）。
