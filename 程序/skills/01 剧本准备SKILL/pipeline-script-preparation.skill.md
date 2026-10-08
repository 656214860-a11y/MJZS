---
name: pipeline-script-preparation
displayName: 全流程AIGC·剧本
description: 锁定创作前提并产出可供结构化处理的自然剧本与创意简报
stage: 剧本准备
capabilities: [creative-writing, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [script.generate, script.validate]
dependsOn: []
conflictsWith: []
parallelizable: false
paid: false
input: [creativeBrief, modelLock, aspectRatio]
output: [scriptRaw, creativeBrief, emotionCurve]
constraints: [确认交付形态前不启动, 不覆盖已确认剧本, 产物通过剧本契约]
feedback:
  - onProgress: 更新剧本准备进度
  - onError: 说明缺失前置输入或契约失败
  - onComplete: 报告自然剧本与简报已就绪
examples:
  - 根据创意简报输出可结构化的自然剧本
---

## 阶段职责

先确认交付形态，逐阶段形成可审阅的自然剧本和简报。模型与画幅在本阶段仅作建议值，但不得擅改用户已确认的要求；不替下游生成分镜、资产或媒体。

## 分阶段输出

1. 先问清楚，再创作：用户未提供故事大体环境和小说/漫剧类型时，必须先问，不能直接写。
2. 每个关键阶段都必须用户确认，不能自动跳到下一阶段。

按①项目设定 → ②剧本大纲 → ③角色卡 → ④自然剧本推进；信息齐全的首轮只输出项目设定。续轮根据对话历史识别当前阶段，用户要求修改则停留当前阶段，明确确认通过才进入下一阶段。每轮只输出当前阶段一个文件，末尾“待确认”，不一次输出多阶段。

定向使用 [jingju 阶段输出模板](../00全流程SKILL/jingju-skills/references/stage-output-contracts.md) 的前四段：项目设定、剧本大纲、角色卡、分集剧本；“分集剧本”对应本阶段完整自然剧本，按集组织正文。角色卡仅作文字参考，不生成参考图；模板所述分镜及以后阶段不在本阶段执行。

项目设定和角色卡存入既有规范的“项目设定”目录，剧本大纲存入“项目大纲”目录；角色卡标明“人物设定”，更新同一路径时保留已确认的项目设定。前三项仅供用户审阅参考，不进入 02 结构剧本的输入，不替代结构化档案。
完整自然剧本是唯一正式交付，落既有规范的“项目剧本”目录，是 02 结构剧本的唯一来源；`character_manifest` 仍由 02 从自然剧本提取。`script_raw.md` 是可继续更新的内部工作稿，正式交付以任务书提供的规范路径为准，不自行另造目录或文件名。

## 定向注入（00 包）

以下是内部质量方法，不是另起一套用户交付阶段，也不授权跳过确认。随当前阶段逐步落实，完成自然剧本前完整遵循五阶门控，不裁剪 Gate：

1. **剧本五阶门控与去机械感**：Premise→Structure→Beat→Entity→Page。
   → [screenplay-gate-engine.md](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md)

2. **情绪节拍曲线**：自然剧本成稿后，量化 12 个关键节拍，产出辅助质检数据 `emotion_curve.json`；它不另设确认阶段，也不替代当前阶段供用户审阅的一个文档。
   → [emotion-beat-curve.md](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/emotion-beat-curve.md#一-12-关键节拍点量化模型010-分)
   第 9 节拍须为全片最高峰且不低于 9.5。

3. **台词七维诊断**：台词写成后自检、修订；除非用户要求诊断，不向自然剧本追加原句／改写／理由的诊断模板。
   → [dialogue-doctor-7d.md](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/dialogue-doctor-7d.md)

4. **台词语速自检**：按语气与语速估算对白时长、调整台词；参考中的拆镜、机位和镜头时限规则留给后续分镜阶段，不在此输出镜头方案。
   → [dialogue-speed-check.md](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/dialogue-speed-check.md)

不得加载 00 包全文、风格库或无关 reference；需要特定类型或导演风格时，另由用户明确选择后才定向读取对应单一文件。
