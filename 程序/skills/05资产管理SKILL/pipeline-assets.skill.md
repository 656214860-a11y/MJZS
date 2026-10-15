---
name: pipeline-assets
displayName: 全流程·资产管理
description: 基于分镜初稿建立角色场景道具正典与可追溯资产清单
stage: 资产管理
capabilities: [vision, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [asset.plan, asset.validate]
dependsOn: [pipeline-animatic]
conflictsWith: []
parallelizable: false
paid: false
input: [storyboardDraft, assetRequirements, characterManifest, sceneManifest, propManifest, sceneBreakdown, emotionCurve]
output: [assetManifest, canonBoard, anchors]
constraints: [资产由剧本与分镜事实导出, 记录版本与来源, 不覆盖已确认资产]
feedback:
  - onProgress: 更新资产管理进度
  - onError: 报告资产需求与正典冲突
  - onComplete: 报告资产清单与锚点已就绪
examples:
  - 从分镜需求建立角色场景道具的正典资产清单
---

## 本阶段读取的项目锁

`track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`reference_mode`（仅 Seedance 2.5）、`splice_mode`、`style_base`／`style_directors`。由剧本准备填写，本阶段直接读取项目设置，不再向用户弹问锁。项目设置优先于引用包内的问答式锁定流程；选填项为空按包内默认处理并在交付中声明，必填项缺失记为配置缺口并返回准备阶段，不擅设默认。非 2.5 不套用 `reference_mode`。

这些声明同样约束本阶段小 SKILL；仅采用与当前赛道、素材来源和任务相关的章节。总控仍可替换，保留既有调试、手动执行和人工裁决入口，不以本次适配新增执行门禁。

## V7.4.20 按职责引用

- [资产工作流程（含素材形态与出图授权）](../00全流程SKILL/AIGC创作全流程/sd-asset-engine/SKILL.md#四工作流程五步)。保持既有稳定资产 ID、正典与 manifest 路径，不把包内示例图号覆盖为项目主键。
- 每次声明素材形态：M0 交文字档案、不编图号；M1 交提示词、编号与素材接线单；M2 仅对实际入库可读图片建图册并核验。缺图片不阻断 M0/M1 文本交接，未看图不得声称图像核验完成。
- 默认只出提示词，不因全流程或本阶段启动自动出图；实际出图须有明确出图授权，沿用既有候选确认、预算与执行器。

引用仅作为相应职责的方法来源，不授予跨阶段执行权限；以下项目交付契约与锁读取规则优先于引用章节中的交互流程及示例输出路径。


## 阶段职责

执行全流程资料中的 Asset-First 资产锁定：把初步分镜的实体需求变为可追溯资产、正典板和连续性锚点。

## 定向注入（00 包）

执行本阶段时，只按需读取 [continuity-bible.md 的 Identity string contract](../00全流程SKILL/cinematic-director/references/continuity-bible.md#the-identity-string-contract)、[Character schema](../00全流程SKILL/cinematic-director/references/continuity-bible.md#character-schema) 与 [Asset naming convention](../00全流程SKILL/cinematic-director/references/continuity-bible.md#asset-naming-convention)，把剧本和分镜事实固化为有来源、版本和稳定身份串的资产正典；读取 [image-model-adapters.md 的 Character consistency playbook](../00全流程SKILL/cinematic-director/references/image-model-adapters.md#4-character-consistency-playbook-cheapest-first)，根据已选工具的控制面决定参考图、种子或编辑约束。

资产缺少可追溯来源、身份锚点或版本时不得进入正典；发现冲突只生成待修复项，不覆盖已确认资产。4 View／16 项资产锁按资产引擎的总控权威链核对；T1→T3 亲缘推导须有当前已选总控的对应依据，缺依据时保留待核验，不得声称已验证。

未完成上述核验时，不能把它们伪装为本阶段已验证规则。

不得加载 00 包全文、风格库或示例库；只有用户明确选择风格时才按需读取对应的单一风格 reference。
