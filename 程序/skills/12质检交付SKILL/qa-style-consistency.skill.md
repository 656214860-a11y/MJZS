---
name: qa-style-consistency
displayName: 风格一致性检查
description: 把成片与风格锚点逐镜比一遍，偏差大的镜列出来
stage: 质检与交付
capabilities: [vision]
preferredModels: [qwen-max, gpt-4o]
fallbackModels: [deepseek-v4-pro]
tools: [qa.styleCheck, qa.visualCheck]
dependsOn: [qa-overall-check]
conflictsWith: []
parallelizable: true
paid: false
input: [composedVideo, style]
output: [styleReport]
constraints: [与风格锚点比对, 逐镜给分, 偏差大的列出来]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："整集风格统一吗" → qa.styleCheck({ master })
  - 用户："哪一镜看着不像同一个剧" → qa.compareStyleAnchors({ master })
---

## 说明
### 这个 SKILL 干什么
整集看下来有没有「某一镜像换了个剧」的情况：按定稿时锁下的风格锚点逐镜比对，色温、
光影、人物与场景一致性都给一个分，偏得多的挑出来。

### 具体做四件事
1. 取锚点：读定稿时锁下的风格锚点与角色参考图。
2. 逐镜比：对色温、光影、人物长相与场景质感各给分。
3. 找离群：偏离整集中位数最多的几镜标出来。
4. 出报告：逐镜分数 ＋ 离群镜头的对比说明。

### 什么时候用它
- 成片看完觉得「有一镜怪怪的」。
- 交付前的最后一道风格关。

### 输入／输出
- 输入：成片、风格锚点与角色参考。
- 输出：风格检查报告（逐镜分数与离群镜头）。

### 用到的工具
- `qa.styleCheck`：11 质检与交付 → 风格检查
- `qa.visualCheck`：11 质检与交付 → 画面质检：逐镜比技术项

### 约束与验收
- 以锚点为准：不许拿某一镜当基准去改别的镜的分。
- 离群镜头要给出对比说明（差在哪一项）。
- 只报不改：要不要重做那一镜由用户定。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
