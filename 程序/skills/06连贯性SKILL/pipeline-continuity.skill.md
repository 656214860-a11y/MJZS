---
name: pipeline-continuity
displayName: 全流程·连贯性清单
description: 审核分镜与资产正典之间的角色场景道具和时空连续性
stage: 连贯性清单
capabilities: [structured-output]
preferredModels: []
fallbackModels: []
tools: [continuity.buildLedger, continuity.audit, continuity.validate]
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

`track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`reference_mode`（仅 Seedance 2.5）、`splice_mode`、`style_base`／`style_directors`。由剧本准备填写，本阶段直接读取项目设置，不再向用户弹问锁。项目设置优先于外部 SKILL 的问答式锁定流程；选填项为空仅采用当前已选 SKILL 明示且适用的默认；没有依据则保持未设置并在交付中声明，必填项缺失记为配置缺口并返回准备阶段，不擅设默认。非 2.5 不套用 `reference_mode`。

这些声明同样约束本阶段小 SKILL；仅采用与当前赛道、素材来源和任务相关的章节。已安装的 SKILL 可由用户选换，保留既有调试、手动执行和人工裁决入口，不以本次适配新增执行门禁。

## 本阶段方法与交付边界

- 跨镜／跨集状态台账。入口状态→变化→退出状态与现有 continuity_ledger、repairList 对齐；冲突路由责任阶段，不代改资产。
- 按 M0 文字档案、M1 编号册与接线单、M2 已入库图册审计；没有图片不等于缺失文本输入，M0/M1 不作已看图核验声明。

本阶段方法不授予跨阶段执行权限；项目交付契约与锁读取规则优先。外部 SKILL 仅在用户选择后使用，不预设已安装包。


## 阶段职责

将已冻结资产与分镜初稿交叉核验，建立连续性台账和可复核的冲突修复项，是分镜定稿的硬前置。

## 执行方式（以实现为准）

本阶段由程序按规则现场计算（`continuity_ledger.build`），不调用模型，不读图；因此本 SKILL 不声明模型偏好，也不要求 reasoning／vision 能力。台账落盘为 `06连贯性清单/output/continuity_ledger.json`；`repairList` 是该阶段冲突修复项的统称，落盘对应物为 `06连贯性清单/output/continuity_issues.json`（问题闭环登记），不存在名为 `repairList` 的独立文件。手动按钮与三虎自动链共用同一个生成实现。

## 阶段核验方法

执行本阶段时，按以下职责核验：The continuity axes、Shot-to-shot continuity schema 与 State-change ledger，将角色、服装、道具、地点、方向与状态变化定位到镜头和资产；核验：F7 Continuity break across shots 与 F19 Object permanence break，以可复核根因和修复项而非静默改写处理漂移。

未解决冲突必须保留到 `repairList`，不得绕过审计进入定稿；本阶段不取得 D 锁的段缝放行权，也不执行分镜定稿放行。

D 锁是项目 `splice_mode`（段缝衔接方式），由剧本准备填写，本阶段只读取并核对连续性；分镜定稿的放行仍以资产与连续性台账通过为依据，不能将 D 锁当作放行权限。

连续性与对象恒存问题必须定位到镜头、状态差异及来源，审计职责保持不变。

不默认加载外部包、风格库或示例库；调试、人工裁定与 SKILL 选换入口保持可用。
