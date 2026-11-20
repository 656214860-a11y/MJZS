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

`track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`reference_mode`（仅 Seedance 2.5）、`splice_mode`、`style_base`／`style_directors`。由剧本准备填写，本阶段直接读取项目设置，不再向用户弹问锁。项目设置优先于外部 SKILL 的问答式锁定流程；选填项为空仅采用当前已选 SKILL 明示且适用的默认；没有依据则保持未设置并在交付中声明，必填项缺失记为配置缺口并返回准备阶段，不擅设默认。非 2.5 不套用 `reference_mode`。

这些声明同样约束本阶段小 SKILL；仅采用与当前赛道、素材来源和任务相关的章节。已安装的 SKILL 可由用户选换，保留既有调试、手动执行和人工裁决入口，不以本次适配新增执行门禁。

## 本阶段方法与交付边界

- 初步分镜工作流程。将镜头方法映射到既有镜头编号和初稿结构，不直接执行其后续投喂、出图或定稿。
- 仅打戏段追加 攻防节拍；玄幻段使用 玄幻攻防设计；写实格斗段使用 写实拆招与镜头设计。只采用当前段对应方法，封装与 PREVIS 留给后续阶段。
- 决策引擎：情境选型与雷区判定：以 01 自然剧本的「本集节拍表」为输入，不重新切分节拍；节拍表缺失时才按本地节拍定义就地补切，并在初稿 `beat_source` 声明来源。逐节拍按 选 ID 优先级流程 选 E-ID（只认 E01–E15 或用户授权后自定义的 EX01，禁止编造；查不到先询问用户），按 80/15/5 权重机制 分配 80/15/5，按 雷区自查流程 逐镜判定。结果落在分镜初稿 JSON 同文件：每镜带 `beat_no`（`场<场次>-节拍<编号>`）、`context_id`、`forbidden_limits`（B 类「限制：…」逐条，无则空数组），顶层按 6 列标准格式 写 `emotion_anchor_table`，并写 `beat_source`、一句 `shot_count_decision`；有雷区时附 `forbidden_zone_report`。追溯字段只作机器元数据，不写进 `frame_prompt`／`video_prompt` 正文；景别阶梯跃迁与机位配额仍以既有权威为准。
- 上一条的「分镜初稿 JSON」指实际工作稿 `03初步分镜/分镜拆分/EP…_分镜.json`；程序派生的 `storyboard_draft.json` 只是已采用索引，不承载锚点表。

本阶段方法不授予跨阶段执行权限；项目交付契约与锁读取规则优先。外部 SKILL 仅在用户选择后使用，不预设已安装包。


## 阶段职责

使用已结构化的剧情事实拆场和拆镜，输出尚未采用的分镜初稿及资产需求，供资产阶段冻结正典。场次拆分产物 `scene_breakdown.json` 按契约落剧本阶段区。

## 阶段核验方法

执行本阶段时，按以下职责核验：Blocking notation 与 Blocking for AI video，把人物位置、朝向、视线、入／出画与动作节拍写成可审核的镜头调度；并核验：Shot functions 与 Continuity geometry，让每个镜头先声明戏剧职责，并标出轴线、屏幕方向或视线的风险。

这里只做段缝风险预检：资产正典和连续性台账尚未冻结时，不能把预检当作放行锁。缺少镜头职责、可执行调度或风险标注时退回结构稿／初稿修订；不越权生成最终提示词或采用分镜。

不默认加载外部包、风格库或示例库；只有用户明确选定风格时，才按需读取被选中的单一风格 reference。

## 情境与追溯的本地定义

基础情境优先，E01–E12不匹配才用E13–E15；仍不匹配须取得用户授权后定义EX01，不能编造其他编号：

| ID | 情境 | 核心组合 |
|---|---|---|
| E01 | 主角觉醒 | 中景、低角仰拍、缓推 |
| E02 | 反派登场 | 全景、低角、逆光剪影、静态 |
| E03 | 紧张追逐 | 手持呼吸感、长焦、快切 |
| E04 | 审讯对峙 | 正面居中、长焦、静态 |
| E05 | 孤独沉思 | 长焦、大光圈、空旷留白 |
| E06 | 暴怒爆发 | 全景、大光圈、手持快摇 |
| E07 | 暧昧试探 | 长焦、大光圈、过肩静态 |
| E08 | 内向退缩 | 过肩、长焦、手持微动 |
| E09 | 突破内心 | 长焦、仰拍、缓推 |
| E10 | 仪式威严 | 对称居中、长焦、静态 |
| E11 | 干脆决断 | 微距标点、静切动 |
| E12 | 释放释怀 | 中景、俯拍、拉远、大景深 |
| E13 | 异化失控 | 强对称居中、全景、缓推；慎用 |
| E14 | 被困压抑 | 头顶贴边、全景、静态 |
| E15 | 神性显现/顿悟 | 背景过亮、逆光剪影、缓升 |

80/15/5是设计权重，不是镜头数量配额：保留核心组合；辅助从相邻焦段、微仰俯、虚化前景、光线、微运动、空间压迫、细节插入中选1–2项；增强仅用于最高情绪峰值、每段最多一镜，可选滑动变焦、环绕、极限景别跳跃、升降或慢动作定格，服从既有景别和机位约束。

情绪锚点六列表：节拍号／4–6字具体情绪词／一句具体剧本动作／情境ID／核心组合摘要／解锁雷区及理由。每段3–5节拍且有变化；每镜对应节拍，每节拍至少一个主镜头体现核心组合。

B类限制逐项规避：物体穿身、服装发型突变、刺眼异物前景、人体比例/手指错误、背景重复无主次、主体周围空白无支撑、道具状态突变。正面居中、头顶贴边、死压中线、视线无留白、切关节、背景过亮、多人正面平铺属于须论证的构图选择，艺术性使用须有情境理由和配套约束，E-ID不能自动免检。
