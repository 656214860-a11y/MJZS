---
name: subtitle-format-export
displayName: 字幕格式导出
description: 把对齐好的字幕导出成 SRT 与 ASS 等各平台要的格式
stage: 配音与字幕
capabilities: [structured-output]
preferredModels: [deepseek-v4-flash]
fallbackModels: [deepseek-v4-pro]
tools: [subtitle.generate, subtitle.syncCheck]
dependsOn: [subtitle-auto-align]
conflictsWith: []
parallelizable: true
paid: false
input: [subtitleFile, formats]
output: [exportedFiles]
constraints: [时间码不重叠, 统一 UTF-8 编码, 平台规范适配]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："导出 SRT 给剪辑" → subtitle.exportSrt({ subtitleFile })
  - 用户："顺带出一份带样式的 ASS" → subtitle.exportAss({ subtitleFile })
---

## 说明
### 这个 SKILL 干什么
对齐好的字幕要交出去：竖屏平台的、剪辑软件的、审片用的各要一种格式。这一步按目标格式
导出来，顺带把时间码倒挂、重叠与超长行检查一遍。

### 具体做四件事
1. 读字幕：取出对齐好的时间码与文本。
2. 查硬错：时间码倒挂、重叠、字幕行过长（超过 18 字）逐条报。
3. 按格式导：SRT、ASS 与自定义分隔符各导一份，编码统一 UTF-8。
4. 出清单：导出文件列表与行数，附检查结果。

### 什么时候用它
- 字幕对了，要交给剪辑或直接上传。
- 同一集要发多个平台，得一次导好几份。

### 输入／输出
- 输入：对齐好的字幕文件、目标格式。
- 输出：各格式的导出文件（含检查结果）。

### 用到的工具
- `subtitle.generate`：09 配音与字幕 → 生成字幕
- `subtitle.syncCheck`：字幕落在本镜时长内、串行不重叠

### 约束与验收
- 时间码不许倒挂或重叠：查出来先修再导。
- 统一 UTF-8：别的编码在平台上会变乱码。
- 导出只加不改：原字幕文件留着不动。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
