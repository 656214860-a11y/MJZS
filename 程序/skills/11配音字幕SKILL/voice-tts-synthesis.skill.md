---
name: voice-tts-synthesis
displayName: TTS 配音合成
description: 多角色 TTS 配音合成，检查音量、语速、情感
stage: 配音与字幕
capabilities: []
preferredModels: []
fallbackModels: []
tools: [voice.synthesize, voice.qualityCheck, voice.retry]
dependsOn: [script-character-extraction]
conflictsWith: []
parallelizable: true
paid: true
input: [projectId, script, characterVoices]
output: [audioTracks, qualityReport]
constraints: [付费步骤提交前确认, 音量/语速/情感合格]
feedback:
  - onProgress: 更新三虎进度
  - onError: 不合格自动重生成
  - onComplete: 通知并推进阶段
examples:
  - 用户："生成所有配音" → voice.synthesize()
  - 用户："重新生成第3镜配音" → voice.synthesize([3])
---

## 说明
### 这个 SKILL 干什么
按剧本的对白做多角色配音：一个角色一个声线，检查音量、语速与情感，不合格的重生成。

### 具体做五件事
1. 拆对白：按说话人把每一句分出来，标出镜头号与大致时长。
2. 定声线：每个角色配一个声音（音色、语速、情感基调），同一角色全片一致。
3. 合成：逐句生成音频，按镜头拼成音轨。
4. 检查：音量归一、语速在可听区间、情感与场次匹配、有没有爆破音与断句错误。
5. 不合格的重生成，并把每句音频与镜头对应起来。

### 什么时候用它
- 配音与字幕页点「手动制作配音」（或勾上自动档）。
- 只想重做某几镜：勾选后重跑，只覆盖这几镜的音轨。

### 输入／输出
- 输入：项目、剧本对白、每个角色的声线设定。
- 输出：音轨（按镜头）与质量报告（音量／语速／情感）。

### 用到的工具
- `voice.synthesize`（09 配音与字幕 → 手动制作配音）
- `voice.qualityCheck`／`voice.retry`（检查与重试）
- 配音接口（TTS）在阶段配置面板的「接口」里选。

### 约束与验收
- 这一步要花钱：提交前确认一次。
- 同一角色跨场声音不许变；一句不超时，超时的先拆句。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
