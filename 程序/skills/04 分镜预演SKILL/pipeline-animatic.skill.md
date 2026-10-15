---
name: pipeline-animatic
displayName: 全流程·分镜预演
description: 用共享参考图和本地草图验证节奏、时长与对白同步
stage: 分镜预演
capabilities: [vision, structured-output, reasoning]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [animatic.generate, animatic.validate]
dependsOn: [pipeline-storyboard-draft]
conflictsWith: []
parallelizable: true
paid: false
input: [storyboardDraft, sharedReferences, temporaryAudio]
output: [animaticManifest, animaticVideo, shotSketches, sharedReferences]
constraints: [仅本地预演草图, 不替代正式资产或首帧或正式视频, 资产提示词仍归资产管理]
feedback:
  - onProgress: 更新分镜预演进度
  - onError: 保留已知任务状态并转人工核查
  - onComplete: 提示人工确认节奏、时长和对白同步
examples:
  - 导入参考图，以本地 ComfyUI 逐镜生成草图并配临时音频合成预演
---

## 本阶段读取的项目锁

`track`、`material_source`、`aspect_ratio`、`resolution`、`fps`、`delivery_format`、`video_model_version`、`reference_mode`（仅 Seedance 2.5）、`splice_mode`、`style_base`／`style_directors`。由剧本准备填写，本阶段直接读取项目设置，不再向用户弹问锁。项目设置优先于引用包内的问答式锁定流程；选填项为空按包内默认处理并在交付中声明，必填项缺失记为配置缺口并返回准备阶段，不擅设默认。非 2.5 不套用 `reference_mode`。

这些声明同样约束本阶段小 SKILL；仅采用与当前赛道、素材来源和任务相关的章节。总控仍可替换，保留既有调试、手动执行和人工裁决入口，不以本次适配新增执行门禁。

## V7.4.20 按职责引用

- [SHOT_TEXT 线稿卡](../00全流程SKILL/AIGC创作全流程/sd-storyboard-engine/SKILL.md#七二shot_text-分镜线稿卡可选产出--给人看)、[坐标系与文字平面图](../00全流程SKILL/AIGC创作全流程/short-drama-director/references/blocking-direction.md#一场景坐标系与文字平面图解禁--这是站位老大难的根因修复)。验证轴线、站位、走位与节拍；线稿卡和文字平面图不冒充已生成媒体。
- 包内默认只产提示词；本项目已有的共享参考、低负载草图、临时音轨与可播放 Animatic 功能保留，由明确启动的预演任务及既有 SG-A／SG-B 流程执行，不因加载引用自动出图。

引用仅作为相应职责的方法来源，不授予跨阶段执行权限；以下项目交付契约与锁读取规则优先于引用章节中的交互流程及示例输出路径。


## 阶段契约

SG-A 核验初步分镜。准备共享参考图（用户导入或本地 ComfyUI 草图），按分镜提示词、参考图与固定种子生成每镜预演图。
复用临时 TTS 或导入音频，经应用内时间线合成生成可播放 Animatic，交 L3 校验、原子发布、索引更新；失败回滚。
按 batch 并行，上限 3，批内串行；明确失败重试 2 次后转人工，提交结果不确定不得自动重投。
SG-B 必须确认节奏、时长、对白同步，生成成功本身不表示确认。需要剪映时另行交接，不声称剪映自动导出。

共享参考图路径仅由 stage_path_service 提供。资产管理复用参考图与生成功能，走线上 API 生成正式资产；资产提示词、正典板、锚点与 assets.json 语义不变。
所有新阶段路径由 stage_path_service 提供，旧编号目录只读兼容，不搬移、不删除用户数据。禁止把预演图登记成正式资产、首帧或正式视频。
