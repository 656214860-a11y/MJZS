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

## 阶段职责

使用已结构化的剧情事实拆场和拆镜，输出尚未采用的分镜初稿及资产需求，供资产阶段冻结正典。场次拆分产物 `scene_breakdown.json` 按契约落剧本阶段区。

## 定向注入（00 包）

执行本阶段时，只按需读取 [blocking-and-staging.md 的 Blocking notation](../00全流程SKILL/cinematic-director/references/blocking-and-staging.md#blocking-notation) 与 [Blocking for AI video](../00全流程SKILL/cinematic-director/references/blocking-and-staging.md#blocking-for-ai-video)，把人物位置、朝向、视线、入／出画与动作节拍写成可审核的镜头调度；再读取 [cinematic-language.md 的 Shot functions](../00全流程SKILL/cinematic-director/references/cinematic-language.md#shot-functions) 与 [Continuity geometry](../00全流程SKILL/cinematic-director/references/cinematic-language.md#continuity-geometry)，让每个镜头先声明戏剧职责，并标出轴线、屏幕方向或视线的风险。

这里只做段缝风险预检：资产正典和连续性台账尚未冻结时，不能把预检当作放行锁。缺少镜头职责、可执行调度或风险标注时退回结构稿／初稿修订；不越权生成最终提示词或采用分镜。

不得加载 00 包全文、风格库或示例库；只有用户明确选定风格时，才按需读取被选中的单一风格 reference。
