---
name: pipeline-continuity
displayName: 全流程·连贯性清单
description: 审核分镜与资产正典之间的角色场景道具和时空连续性
stage: 连贯性清单
capabilities: [structured-output, reasoning, vision]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [continuity.audit, continuity.validate]
dependsOn: [pipeline-assets]
conflictsWith: []
parallelizable: false
paid: false
input: [storyboardDraft, assetManifest, anchors]
output: [continuityLedger, repairList]
constraints: [所有冲突可定位到镜头或资产, 不擅自改写正典, 未解决冲突不得进入定稿]
feedback:
  - onProgress: 更新连贯性审计进度
  - onError: 报告阻塞性连续性冲突
  - onComplete: 报告连续性台账与修复清单已就绪
examples:
  - 审核角色服装和道具在相邻镜头中的连续性
---

## 本阶段读取的项目锁

`track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`reference_mode`（仅 Seedance 2.5）、`splice_mode`、`style_base`／`style_directors`。由剧本准备填写，本阶段直接读取项目设置，不再向用户弹问锁。项目设置优先于引用包内的问答式锁定流程；选填项为空按包内默认处理并在交付中声明，必填项缺失记为配置缺口并返回准备阶段，不擅设默认。非 2.5 不套用 `reference_mode`。

这些声明同样约束本阶段小 SKILL；仅采用与当前赛道、素材来源和任务相关的章节。总控仍可替换，保留既有调试、手动执行和人工裁决入口，不以本次适配新增执行门禁。

## V7.4.20 按职责引用

- [跨镜／跨集状态台账](../00全流程SKILL/AIGC创作全流程/sd-qc-engine/SKILL.md#1-连续性检查跨镜跨集)。入口状态→变化→退出状态与现有 continuity_ledger、repairList 对齐；冲突路由责任阶段，不代改资产。
- 按 M0 文字档案、M1 编号册与接线单、M2 已入库图册审计；没有图片不等于缺失文本输入，M0/M1 不作已看图核验声明。

引用仅作为相应职责的方法来源，不授予跨阶段执行权限；以下项目交付契约与锁读取规则优先于引用章节中的交互流程及示例输出路径。


## 阶段职责

将已冻结资产与分镜初稿交叉核验，建立连续性台账和可复核的冲突修复项，是分镜定稿的硬前置。

## 定向注入（00 包）

执行本阶段时，只按需读取 [continuity-bible.md 的 The continuity axes](../00全流程SKILL/cinematic-director/references/continuity-bible.md#the-continuity-axes)、[Shot-to-shot continuity schema](../00全流程SKILL/cinematic-director/references/continuity-bible.md#shot-to-shot-continuity-schema) 与 [State-change ledger](../00全流程SKILL/cinematic-director/references/continuity-bible.md#state-change-ledger)，将角色、服装、道具、地点、方向与状态变化定位到镜头和资产；读取 [failure-modes.md 的 F7 Continuity break across shots](../00全流程SKILL/cinematic-director/references/failure-modes.md#f7--continuity-break-across-shots) 与 [F19 Object permanence break](../00全流程SKILL/cinematic-director/references/failure-modes.md#f19--object-permanence-break对象消失)，以可复核根因和修复项而非静默改写处理漂移。

未解决冲突必须保留到 `repairList`，不得绕过审计进入定稿；本阶段不取得 D 锁的段缝放行权，也不执行分镜定稿放行。

D 锁是项目 `splice_mode`（段缝衔接方式），由剧本准备填写，本阶段只读取并核对连续性；分镜定稿的放行仍以资产与连续性台账通过为依据，不能将 D 锁当作放行权限。

旧定位 `failure-modes.md#f7-continuity-break-across-shots` 已迁移到上文 F7 的有效章节锚点；审计职责保持不变。

不得加载 00 包全文、风格库或示例库；调试、人工裁定与统筹替换入口保持可用。
