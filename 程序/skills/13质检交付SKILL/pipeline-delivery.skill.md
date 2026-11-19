---
name: pipeline-delivery
displayName: 全流程·质检与交付
description: 核验成片字幕和清单并输出交付报告与可恢复交付包
stage: 质检与交付
capabilities: [structured-output, reasoning, vision]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [delivery.validate, delivery.package]
dependsOn: [pipeline-editing]
conflictsWith: []
parallelizable: false
paid: false
input: [previewMaster, editManifest, subtitles, audioManifest]
output: [qualityReport, deliveryPackage, deliveryManifest]
constraints: [质检报告列出失败项, 交付包可追溯来源, 未通过质检不得标记交付完成]
feedback:
  - onProgress: 更新质检交付进度
  - onError: 报告质量阻塞与返工入口
  - onComplete: 报告交付包和验收结果
examples:
  - 对成片字幕与清单执行质检并生成交付包
---

## 阶段职责

执行全流程的最终质量门禁，输出可审计质检报告、交付包和交付清单；失败项保留为可追踪返工依据。

## 本阶段读取的项目锁

直接读取项目创作信息窗／阶段配置中由「剧本准备」填写的 `track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`splice_mode`、`style_base`、`style_directors`；`reference_mode` 仅在 Seedance 2.5 时读取并按该版本校验。赛道与来源用于继承创作上下文，规格、模型、段缝和风格用于本阶段产物及验收。
项目设置优先于外部 SKILL 的交互询问、默认推荐及独立调用示例；后续阶段直接读取，不再向用户弹问或重新收集锁。必填锁缺失或矛盾时记录缺项并退回剧本准备／项目配置补齐，不擅填默认值；选填空值仅采用当前已选 SKILL 明示且适用的默认；没有依据则保持未设置，在本阶段清单及最终交付中声明采用值和依据，不把空值当成用户已选风格卡。此规则不取消既有制作授权、预算和人工复核要求，也不关闭调试、手动执行或 SKILL 选换入口。

## 本阶段方法与交付边界

按 连续性核对、转场检查、声音检查 组织成片复核，按 出稿机检 和 统一裁决 分别记录硬性失败与建议项。
该引擎的出稿机检只证明稿件层检查结果，不能替代本阶段真实成片、音轨、字幕与交付文件验收。M0/M1 文本交付按声明形态核对，不索要不存在的图片；交付形态若要求实际成片，则必须有真实可播放媒体，不能用稿件或占位清单放行。

本文件直接定义本阶段职责；外部 SKILL 不能覆盖项目锁及阶段交付边界。

## 阶段核验方法

执行本阶段时，按以下职责核验：60-second triage tree、The cost ladder、Failure taxonomy F1–F19，以及 The assembly spec 和 Seed and reference registry。把观察到的症状记录为可追溯的 F 码、时间码和返工入口，并核对交付清单能追溯至剪辑、媒体、种子和参考资产。

任一质量项未通过、失败项未列入 `qualityReport`、或交付包与 `deliveryManifest` 无法回溯来源时，不得标记交付完成；返工应保留最小可执行入口，不得用“已交付”掩盖未解决的失败码。

不默认加载外部包、风格库或示例库；调试、人工复核与 SKILL 选换入口保持可用。

## 故障分类与返工

F1身份漂移；F2无运动/PPT感；F3几何扭曲/融化；F4动作错误或缺失；F5无明确终态；F6镜头混乱/擅自运动；F7跨镜连续性断裂；F8时代泄漏；F9凭空增加人/物；F10手肢眼齿解剖错误；F11文字/水印伪影；F12光色漂移；F13速度/变速异常；F14重力重量碰撞液体等物理错误；F15音画/口型不同步；F16风格漂移；F17取景裁切错误；F18延长/循环接缝；F19既有对象消失。

逐种观察症状记录镜头、时间码、症状、F码、根因与返工入口；不用“假/无聊”代替观察。先修提示或参数，再按原因修首帧、重设镜头或交剪辑；同因失败不无改动盲重试，多故障先简化或拆镜。可通过剪辑修正的局部问题不强制重生，重试与预算沿用程序既有权威。
