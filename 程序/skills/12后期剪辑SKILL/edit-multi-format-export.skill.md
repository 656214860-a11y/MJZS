---
name: edit-multi-format-export
displayName: 多格式导出
description: 按抖音、B站、YouTube 要求导出不同分辨率、比例、码率
stage: 后期剪辑
capabilities: []
preferredModels: []
fallbackModels: []
tools: [edit.exportDouyin, edit.exportBilibili, edit.exportYouTube, edit.exportCustom]
dependsOn: [edit-auto-compose]
conflictsWith: []
parallelizable: true
paid: false
input: [composedVideo, platforms, customParams]
output: [exportedFiles]
constraints: [平台规范适配, 码率/分辨率/比例正确]
feedback:
  - onProgress: 更新三虎进度
  - onComplete: 通知并推进阶段
examples:
  - 用户："导出抖音和B站版本" → edit.exportDouyin() + edit.exportBilibili()
---

## 说明
### 这个 SKILL 干什么
把合成好的成片按各平台的要求导出：抖音、B站、YouTube 的分辨率、比例与码率各来一份，
需要时也能自定义参数。

### 具体做四件事
1. 先读取项目 `aspect_ratio`、`resolution`、`fps`、`delivery_format`，按锁定规格导出并核对平台要求；竖屏 1080×1920／横屏 1920×1080 仅是规格示例，不覆盖项目锁。
2. 需要时补边或裁切，保证不拉伸变形（人物不被切到脸）。
3. 逐个导出并校验：文件能播、时长与成片一致、参数符合平台要求。
4. 可选打包：连同交付清单一起归档。

### 什么时候用它
- 后期剪辑页导出，或质检与交付页出交付包时。
- 换平台发布之前单独导一版。

### 输入／输出
- 输入：合成成片、目标平台清单、自定义参数（可选）。
- 输出：各平台的导出文件（含参数报告）。

### 用到的工具
- `edit.exportDouyin`／`edit.exportBilibili`／`edit.exportYouTube`／`edit.exportCustom`

### 约束与验收
- 参数按平台规范，不用「差不多」的分辨率；平台要求与项目锁冲突时记录冲突，返回项目配置处理，不在本阶段弹问或重填锁。用户明确要求的额外平台版本另存并标明衍生规格，不反写项目主交付锁。
- 导出完必须回读校验（时长、分辨率、音轨），失败的报出来。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
