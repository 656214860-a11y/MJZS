---
name: pipeline-storyboard-final
displayName: 全流程·分镜定稿
description: 根据连续性台账将审核通过的分镜初稿收敛为采用分镜和提示词批次
stage: 分镜定稿
capabilities: [structured-output, creative-writing, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [storyboard.finalize, storyboard.validate]
dependsOn: [pipeline-continuity]
conflictsWith: []
parallelizable: false
paid: false
input: [storyboardDraft, continuityLedger, assetManifest]
output: [adoptedStoryboard, promptBatches]
constraints: [只采用连续性审核通过的镜头, 保留镜头与资产追溯关系, 生成批次标识]
feedback:
  - onProgress: 更新分镜定稿进度
  - onError: 报告未解决的连续性阻塞
  - onComplete: 报告采用分镜与批次已就绪
examples:
  - 将连续性通过的分镜初稿定稿并生成镜头批次
---

## 阶段职责

只以通过审计的资产和连续性台账为依据，发布采用分镜、镜头提示词与批次关系，供首帧制作使用。

## 本阶段读取的项目锁

直接读取项目创作信息窗／阶段配置中由「剧本准备」填写的 `track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`splice_mode`、`style_base`、`style_directors`；`reference_mode` 仅在 Seedance 2.5 时读取并按该版本校验。赛道与来源用于继承创作上下文，规格、模型、段缝和风格用于本阶段产物及验收。
项目设置优先于外部 SKILL 的交互询问、默认推荐及独立调用示例；后续阶段直接读取，不再向用户弹问或重新收集锁。必填锁缺失或矛盾时记录缺项并退回剧本准备／项目配置补齐，不擅填默认值；选填空值仅采用当前已选 SKILL 明示且适用的默认；没有依据则保持未设置，在本阶段清单及最终交付中声明采用值和依据，不把空值当成用户已选风格卡。此规则不取消既有制作授权、预算和人工复核要求，也不关闭调试、手动执行或 SKILL 选换入口。

## 本阶段方法与交付边界

按 分镜工作流程 核对已采用镜头、台词承接和空间事实，不在定稿阶段重写已确认剧情。
投喂前逐项核对：上游材料齐备、素材身份与接线一致、模型与参考模式匹配、对白无遗漏、段缝状态可追溯、输出字段符合本阶段契约。素材形态从上游清单继承：M0 使用文字档案且不写图号；M1 校验编号册与接线单，不把缺实体图片判作缺稿；M2 才核验已入库图片。`material_source` 是素材来源锁，不是 M0/M1/M2。

- 决策引擎：雷区判定流程 与 情绪锚点表格式：定稿阶段不重做镜头选型、不重分配 80/15/5、不补造 E-ID，只逐镜核对 03 初稿的 `beat_no`／`context_id`／`forbidden_limits`（B 类「限制：…」）是否保留；缺失或对不上退回 03 修订。资产对齐清单沿用 `storyboard-asset-sync` 与 `名称编号对照`：以分镜编号为主键，在分镜编号右侧增加一列「节拍＃／E-ID」追溯（取 `beat_no`／`context_id` 组合），再列资产编号；资产编号与分镜编号的锁定、对齐规则本身不变。追溯字段只进清单与镜头元数据，不写进投喂提示词正文。

本文件直接定义本阶段职责；外部 SKILL 不能覆盖项目锁及阶段交付边界。

## 阶段核验方法

执行本阶段时，按以下职责核验：Shot functions，先按目标模型的能力选择可执行的镜头职责与表达形态；每镜按主体与环境事实→主动作→一个主运镜→终态→必要约束组织提示词，把已采用的镜头事实渲染为明确、可追溯的提示词批次，而不是凭“好看”补写语义。

读取已填写的 `splice_mode`（D 锁），在本阶段核验段缝并放行，不重新选锁。

D 锁只在本阶段放行：核验：Shot-to-shot continuity schema 与 State-change ledger，每个段缝必须冻结 `in_state`、`out_state`、`cut_type`、`audio_bridge` 与 `owner`。任一项缺失或与通过审计的资产／连续性台账冲突时，退回修订，不发布采用分镜或提示词批次。

不默认加载外部包、风格库或示例库；用户明确选择风格时才读取单一对应风格 reference，调试、人工复核与 SKILL 选换入口保持可用。
