---
name: pipeline-storyboard-draft
displayName: 全流程·初步分镜
description: 将结构化剧本转为可审核的场次与镜头初稿
stage: 初步分镜
capabilities: [structured-output, creative-writing, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.generate, storyboard.validate]
dependsOn: [pipeline-script-structure]
conflictsWith: []
parallelizable: false
paid: false
input: [structuredScript, characterManifest, sceneManifest, propManifest]
output: [storyboardDraft, assetRequirements, sceneBreakdown]
constraints: [镜头必须对应剧本事实, 标明场次与镜头号, 不生成最终视频提示词]
feedback:
  - onProgress: 更新初步分镜进度
  - onError: 报告缺失的场景或角色事实
  - onComplete: 报告分镜初稿已就绪
examples:
  - 根据结构剧本输出逐场镜头初稿与资产需求
---

## 本阶段读取的项目锁

`track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`reference_mode`（仅 Seedance 2.5）、`splice_mode`、`style_base`／`style_directors`。由剧本准备填写，本阶段直接读取项目设置，不再向用户弹问锁。项目设置优先于引用包内的问答式锁定流程；选填项为空按包内默认处理并在交付中声明，必填项缺失记为配置缺口并返回准备阶段，不擅设默认。非 2.5 不套用 `reference_mode`。

这些声明同样约束本阶段小 SKILL；仅采用与当前赛道、素材来源和任务相关的章节。总控仍可替换，保留既有调试、手动执行和人工裁决入口，不以本次适配新增执行门禁。

## V7.4.20 按职责引用

- [初步分镜工作流程](../00全流程SKILL/AIGC创作全流程/sd-storyboard-engine/SKILL.md#四工作流程)。将镜头方法映射到既有镜头编号和初稿结构，不直接执行其后续投喂、出图或定稿。
- 仅打戏段追加 [攻防节拍](../00全流程SKILL/AIGC创作全流程/sd-combat-engine/SKILL.md#四工作流程五步)；玄幻段使用 [玄幻攻防设计](../00全流程SKILL/AIGC创作全流程/sd-xuanhuan-engine/SKILL.md#四工作流程五步)；写实格斗段使用 [写实拆招与镜头设计](../00全流程SKILL/AIGC创作全流程/sd-real-engine/SKILL.md#四工作流程六步--asset-first-精简版)。只采用当前段对应方法，封装与 PREVIS 留给后续阶段。
- [决策引擎：情境选型与雷区判定](../00全流程SKILL/AIGC创作全流程/sd-decision-engine/SKILL.md#四工作流程)：取步骤 3–6，以 01 自然剧本的「本集节拍表」为输入，不重新切分节拍；节拍表缺失时才按步骤 2 就地补切，并在初稿 `beat_source` 声明来源。逐节拍按 [选 ID 优先级流程](../00全流程SKILL/AIGC创作全流程/sd-decision-engine/references/context-mapping.md#六选-id-的优先级流程) 选 E-ID（只认 E01–E15 或用户授权后自定义的 EX01，禁止编造；查不到先询问用户），按 [80/15/5 权重机制](../00全流程SKILL/AIGC创作全流程/sd-decision-engine/references/context-mapping.md#一80155-权重机制核心) 分配 80/15/5，按 [雷区自查流程](../00全流程SKILL/AIGC创作全流程/sd-decision-engine/references/forbidden-zone-whitelist.md#六雷区自查流程生成完每个大分镜后过) 逐镜判定。结果落在分镜初稿 JSON 同文件：每镜带 `beat_no`（`场<场次>-节拍<编号>`）、`context_id`、`forbidden_limits`（B 类「限制：…」逐条，无则空数组），顶层按 [6 列标准格式](../00全流程SKILL/AIGC创作全流程/sd-decision-engine/references/emotion-anchor-table.md#一标准格式6-列) 写 `emotion_anchor_table`，并写 `beat_source`、一句 `shot_count_decision`；有雷区时附 `forbidden_zone_report`。追溯字段只作机器元数据，不写进 `frame_prompt`／`video_prompt` 正文；景别阶梯跃迁与机位配额仍以既有权威为准。
- 上一条的「分镜初稿 JSON」指实际工作稿 `03初步分镜/分镜拆分/EP…_分镜.json`；程序派生的 `storyboard_draft.json` 只是已采用索引，不承载锚点表。

引用仅作为相应职责的方法来源，不授予跨阶段执行权限；以下项目交付契约与锁读取规则优先于引用章节中的交互流程及示例输出路径。


## 阶段职责

使用已结构化的剧情事实拆场和拆镜，输出尚未采用的分镜初稿及资产需求，供资产阶段冻结正典。场次拆分产物 `scene_breakdown.json` 按契约落剧本阶段区。

## 定向注入（00 包）

执行本阶段时，只按需读取 [blocking-and-staging.md 的 Blocking notation](../00全流程SKILL/cinematic-director/references/blocking-and-staging.md#blocking-notation) 与 [Blocking for AI video](../00全流程SKILL/cinematic-director/references/blocking-and-staging.md#blocking-for-ai-video)，把人物位置、朝向、视线、入／出画与动作节拍写成可审核的镜头调度；再读取 [cinematic-language.md 的 Shot functions](../00全流程SKILL/cinematic-director/references/cinematic-language.md#shot-functions) 与 [Continuity geometry](../00全流程SKILL/cinematic-director/references/cinematic-language.md#continuity-geometry)，让每个镜头先声明戏剧职责，并标出轴线、屏幕方向或视线的风险。

这里只做段缝风险预检：资产正典和连续性台账尚未冻结时，不能把预检当作放行锁。缺少镜头职责、可执行调度或风险标注时退回结构稿／初稿修订；不越权生成最终提示词或采用分镜。

不得加载 00 包全文、风格库或示例库；只有用户明确选定风格时，才按需读取被选中的单一风格 reference。
