---
name: edit-preview-generate
displayName: 预览生成
description: 出一版低码率预览片，按版本比对改动
stage: 后期剪辑
capabilities: []
preferredModels: []
fallbackModels: []
tools: [edit.compose, edit.exportCustom]
dependsOn: [edit-auto-compose]
conflictsWith: []
parallelizable: true
paid: false
input: [composedVideo]
output: [previewVideo]
constraints: [低码率快出, 不动成片, 版本可比对]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："出一版小片我看看" → edit.renderPreview({ master })
  - 用户："跟上一版比改了哪儿" → edit.compareVersions({ versions })
---

## 说明
### 这个 SKILL 干什么
审片不必每次都看原片：抽一版低码率预览，出得快、传得动；再和上一版并列比对，改动一眼
看得出来。

### 具体做四件事
1. 出预览：按成片的时长与画幅压一版小片。
2. 记版本：写清是第几版、改了哪里。
3. 并排比：与上一版摆在一起，标出画面与声音的差异点。
4. 留成片：原片一个字节不动。

### 什么时候用它
- 改了转场或配乐之后想快速看一眼。
- 要把片子发给别人先过一眼（小文件好传）。

### 输入／输出
- 输入：剪好的成片。
- 输出：预览小片、版本比对结果。

### 用到的工具
- `edit.compose`：10 后期剪辑 → 自动合成
- `edit.exportCustom`：10 后期剪辑 → 自定义导出（低码率那一版）

### 约束与验收
- 不动成片：预览是另存的一份。
- 预览要标清是预览：别让人当成终稿发出去。
- 比对结果写人话（改了哪几处），别只报码率与文件大小。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
