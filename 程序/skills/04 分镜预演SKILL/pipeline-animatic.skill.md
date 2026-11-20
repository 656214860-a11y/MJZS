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

本阶段只读取项目已填的画幅锁，并据此生成本地低配预览规格（预览分辨率与帧率固定，见 REQ-S04-04）；不把赛道、素材来源、交付形态、视频模型等其他制作锁当作本阶段输入，也不把它们的缺失当作本阶段的阻断或回退条件。

项目设置优先于外部 SKILL 的问答式锁定流程；引用包中的其他锁只供相应职责的方法参考，不由本阶段读取或校验。选填项为空仅采用当前已选 SKILL 明示且适用的默认；没有依据则保持未设置并在交付中声明，不擅设为正式交付规格。

这些声明同样约束本阶段小 SKILL；仅采用与当前赛道、素材来源和任务相关的章节。已安装的 SKILL 可由用户选换，保留既有调试、手动执行和人工裁决入口，不以本次适配新增执行门禁。

## 本阶段方法与交付边界

- SHOT_TEXT 线稿卡、坐标系与文字平面图。验证轴线、站位、走位与节拍；线稿卡和文字平面图不冒充已生成媒体。
- 本阶段不会因加载说明自动生成媒体；本项目已有的共享参考、低负载草图、临时音轨与可播放 Animatic 功能保留，由明确启动的预演任务及既有 SG-A／SG-B 流程执行，不因加载引用自动出图。

本阶段方法不授予跨阶段执行权限；项目交付契约与锁读取规则优先。外部 SKILL 仅在用户选择后使用，不预设已安装包。


## 阶段契约

SG-A 核验初步分镜。准备共享参考图（用户导入或本地 ComfyUI 草图），按分镜提示词、参考图与固定种子生成每镜预演图。
复用临时 TTS 或导入音频，经应用内时间线合成生成可播放 Animatic，交 L3 校验、原子发布、索引更新；失败回滚。
按 batch 并行，上限 3，批内串行；明确失败重试 2 次后转人工，提交结果不确定不得自动重投。
SG-B 必须确认节奏、时长、对白同步，生成成功本身不表示确认。需要剪映时另行交接，不声称剪映自动导出。

共享参考图路径仅由 stage_path_service 提供。资产管理复用参考图与生成功能，走线上 API 生成正式资产；资产提示词、正典板、锚点与 assets.json 语义不变。
所有新阶段路径由 stage_path_service 提供，旧编号目录只读兼容，不搬移、不删除用户数据。禁止把预演图登记成正式资产、首帧或正式视频。
