---
name: pipeline-video-generation
displayName: 全流程·视频生成
description: 以可播放预演和采用分镜生成可追溯的视频片段与任务清单
stage: 视频生成
capabilities: [vision, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [video.submit, video.validate]
dependsOn: [pipeline-previs]
conflictsWith: []
parallelizable: false
paid: true
input: [previsMedia, previsManifest, promptBatches, keyframes]
output: [videoClips, videoManifest]
constraints: [遵守已锁定模型与画幅, 记录任务状态, 失败片段不伪造完成]
feedback:
  - onProgress: 更新视频生成进度
  - onError: 报告任务失败和可重试状态
  - onComplete: 报告视频片段与清单已就绪
examples:
  - 根据白模预演和镜头批次提交并核验视频片段
---

## 阶段职责

执行已锁定的模型与画幅契约，生成、轮询并核验镜头片段；图生视频／参考模式以首帧为输入依据。该阶段输出是配音字幕与剪辑的共同媒体输入。

## 本阶段读取的项目锁

直接读取项目创作信息窗／阶段配置中由「剧本准备」填写的 `track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`splice_mode`、`style_base`、`style_directors`；`reference_mode` 仅在 Seedance 2.5 时读取并按该版本校验。赛道与来源用于继承创作上下文，规格、模型、段缝和风格用于本阶段产物及验收。
项目设置优先于引用中的交互询问、默认推荐及独立调用示例；后续阶段直接读取，不再向用户弹问或重新收集锁。必填锁缺失或矛盾时记录缺项并退回剧本准备／项目配置补齐，不擅填默认值；选填空值按新版包适用默认处理，在本阶段清单及最终交付中声明采用值和依据，不把空值当成用户已选风格卡。此规则不取消既有制作授权、预算和人工复核要求，也不关闭调试、手动执行或总控替换入口。

## 新版子技能章节（按职责读取）

投喂封装按 [素材映射与锚定](../00全流程SKILL/AIGC创作全流程/sd-feed-engine/SKILL.md#步骤-4--素材映射与人物道具锚定)、[多段衔接](../00全流程SKILL/AIGC创作全流程/sd-feed-engine/SKILL.md#步骤-5--多段衔接策略)、[工程语言清洗](../00全流程SKILL/AIGC创作全流程/sd-feed-engine/SKILL.md#步骤-6--工程语言清洗)、[台词完整性对照](../00全流程SKILL/AIGC创作全流程/sd-feed-engine/SKILL.md#步骤-7--台词完整性对照治格式全对内容漏句)、[闸门检查](../00全流程SKILL/AIGC创作全流程/sd-feed-engine/SKILL.md#步骤-8--过六道闸门)、[输出封装](../00全流程SKILL/AIGC创作全流程/sd-feed-engine/SKILL.md#步骤-9--输出) 执行；M0 不写图号，M1 附接线单且不声称已挂图，M2 只绑定真实登记素材。图像依赖模式的实际提交必须有可用输入，文本稿完成不等于视频生成成功。
按已锁模型选择 [Seedance 2.5／2.0 投喂差异](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/model-adapters.md#1-25-vs-20-投喂法则对照表)、[2.5 提示词范式](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/model-adapters.md#2-seedance-25-三层解耦提示词投喂范式)、[投喂前自检](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/model-adapters.md#三-投喂前自检清单-pre-flight-checklist)；H3 使用 [H3 模式路由](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/h3-adapter.md#一模式路由h3-只有两个-checkpoint别按五模型理解)、[字段映射](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/h3-adapter.md#二七段式--h3-字段映射核心表)、[H3 硬约束](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/h3-adapter.md#三h3-硬约束写死--机检兜底) 和 [投喂载荷](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/h3-adapter.md#五投喂路径与载荷p4-封装)。只应用匹配版本及参考模式的章节，包内规范不是当前供应商接口可用性的实测证明。

本文件仅声明所需章节，不授权加载整个总控包；读取时以项目锁及本阶段职责为边界。

## 定向注入（00 包）

执行本阶段时，只按需读取 [ai-video-tool-adapters.md 的 The capability-first rule](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#the-capability-first-rule)、[The four prompt shapes](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#the-four-prompt-shapes)、[Per-tool adapters](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#per-tool-adapters)、[The motion budget](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#the-motion-budget) 与 [Duration strategy](../00全流程SKILL/cinematic-director/references/ai-video-tool-adapters.md#duration-strategy)：先读取所选工具的控制面，再选择 S1／S2／S3／S4 提示词形态，继承首帧画幅并回填 `videoManifest`。

失败片段按需读取 [failure-modes.md 的 60-second triage tree](../00全流程SKILL/cinematic-director/references/failure-modes.md#60-second-triage-tree) 与 [Failure taxonomy F1–F19](../00全流程SKILL/cinematic-director/references/failure-modes.md#failure-taxonomy-f1f19)，记录可重试根因和任务状态，不能伪造完成。未经所选工具控制面或实际接口核验的 Seedance 2.0／2.5 专有语法及“2.0 禁首尾帧”断言，不能作为已验证规则写入本阶段。

Seedance 2.0／2.5 已有新版包内模型适配参考；版本专有语法按上列对应章节执行，仍须核对实际接口能力，不能把包内说明冒充接口实测。

不得加载 00 包全文、风格库或示例库；调试、人工复核与统筹替换入口保持可用。
