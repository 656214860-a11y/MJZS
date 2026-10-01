---
name: voice-multi-character
displayName: 多角色配音（已合并）
description: 已合并到「TTS 配音合成」；保留此 ID 兼容已有项目配置，不再单独执行
stage: 配音与字幕
capabilities: [structured-output]
preferredModels: [qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: []
dependsOn: []
conflictsWith: []
parallelizable: true
paid: true
deprecated: true
replacedBy: voice-tts-synthesis
input: [script, characterVoices]
output: [audioTracks]
constraints: [一角一音色, 音色与年龄性别相符, 付费前确认]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："给每个角色配个音色" → voice.castCharacters({ episodeId })
  - 用户："整集配一遍" → voice.synthesizeAll({ episodeId })
---

## 说明
### 已合并说明
这个历史 ID 已合并到「TTS 配音合成」。旧项目若仍勾选本项，运行时会自动改用主 SKILL；
新项目默认只显示并执行主 SKILL，避免同一批对白重复合成与重复计费。
