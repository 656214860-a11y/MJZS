---
name: pipeline-script-structure
displayName: 全流程·剧本整理
description: 将已确认自然剧本整理为下游可消费的结构化剧本与要素清单
stage: 剧本结构
capabilities: [structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [script.generate, script.validate]
dependsOn: [pipeline-script-preparation]
conflictsWith: []
parallelizable: false
paid: false
input: [scriptRaw, creativeBrief]
output: [structuredScript, characterManifest, sceneManifest, propManifest]
constraints: [保留原始剧情事实, 提取角色场景道具, 不修改原始剧本]
feedback:
  - onProgress: 更新剧本整理进度
  - onError: 报告无法解析的剧本事实
  - onComplete: 报告结构剧本与清单已就绪
examples:
  - 将自然剧本整理为角色场景道具和分场结构
---

## 本阶段读取的项目锁

`track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`reference_mode`（仅 Seedance 2.5）、`splice_mode`、`style_base`／`style_directors`。由剧本准备填写，本阶段直接读取项目设置，不再向用户弹问锁。项目设置优先于引用包内的问答式锁定流程；选填项为空按包内默认处理并在交付中声明，必填项缺失记为配置缺口并返回准备阶段，不擅设默认。非 2.5 不套用 `reference_mode`。

这些声明同样约束本阶段小 SKILL；仅采用与当前赛道、素材来源和任务相关的章节。总控仍可替换，保留既有调试、手动执行和人工裁决入口，不以本次适配新增执行门禁。

## V7.4.20 按职责引用

- [分集规划与结构位置](../00全流程SKILL/AIGC创作全流程/sd-script-engine/SKILL.md#六阶段链)、[分集规划边界](../00全流程SKILL/AIGC创作全流程/sd-script-engine/SKILL.md#分集选择门)。只整理已确认自然剧本与已选分集，不重开剧本创作和分集选择，不越过本阶段结构化交付契约。

引用仅作为相应职责的方法来源，不授予跨阶段执行权限；以下项目交付契约与锁读取规则优先于引用章节中的交互流程及示例输出路径。


## 阶段职责

承接剧本准备产物，按剧本契约生成结构化正文与角色／场景／道具三类清单，作为分镜和资产的共同事实来源。情绪曲线在剧本准备阶段产出，场次拆分在初步分镜阶段产出。

## 定向注入（00 包）

执行本阶段时，只按需读取 [production-workflow.md 的 The loop 与 Gate 1 · Plan](../00全流程SKILL/cinematic-director/references/production-workflow.md#the-loop)，把自然剧本中的节拍、风格与戏剧职责整理成下游可审阅的事实；计划证据不足时退回剧本准备。
镜头功能、景别或机位等视觉语义需要进入结构稿时，只读取 [cinematic-language.md 的 Shot functions](../00全流程SKILL/cinematic-director/references/cinematic-language.md#shot-functions)，先声明镜头功能，禁止把“好看”作为唯一职责。

不得加载 00 包全文、风格库或示例库；本阶段不越权生成分镜提示词。
