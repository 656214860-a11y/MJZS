---
name: script-character-extraction
displayName: 角色与设定提取
description: 从剧本中提取角色特征、场景列表、道具清单，输出结构化资产需求
stage: 剧本结构
capabilities: [structured-output]
preferredModels: [deepseek-v4-flash, qwen-max]
fallbackModels: [deepseek-v4-pro]
tools: [script.extractCharacters, script.extractScenes, script.extractProps]
dependsOn: [script-structured-generation]
conflictsWith: []
parallelizable: true
paid: false
input: [structuredScript]
output: [characterProfiles, sceneList, propList]
constraints: [角色特征完整, 场景去重, 道具关联角色]
feedback:
  - onProgress: 更新三虎进度
  - onComplete: 通知并推进阶段
examples:
  - 用户："提取所有角色和场景" → script.extractCharacters()
---

## 说明
### 这个 SKILL 干什么
从创意、大纲或剧本正文里把「人物、场景、道具」三类资产认出来，逐个落成资产条目，供后面
资产图片制作、分镜与首帧引用。它是资产链路的起点：这一步漏人漏物，后面每一步都会缺图。

### 具体做四件事
1. 通读剧本，按出场顺序抽出人物（含别名、年纪、身份、关系）与场景（地点、时间、天气）。
2. 抽关键道具（推动剧情的那几件），并标出它首次出场与转手的镜头。
3. 每个条目补一份「外观描述」——写成可以直接交给画师或生图模型的样子，不写心理活动。
4. 与项目里已有的资产清单比对：同一个人／同一处景只留一条，别名合并，不重复建档。

### 什么时候用它
- 刚写好创意或大纲，要先把人物场景备齐再往下走。
- 剧本改过（加人、改名、换场景）之后重新跑一遍，把新条目补进资产表。
- 资产页有「无描述」的条目时，用它重抽一次补齐外观描述。

### 输入／输出
- 输入：剧本或大纲正文（当前项目里最新那一份）、画风与年代设定。
- 输出：资产条目表，每条带类别、名称、别名、外观描述、首次出场位置。
- 落盘：output 下的 character_manifest.json／scene_manifest.json／prop_manifest.json
  （编号分别用 CHAR_／LOC_／PROP_，角色带 physical_features 五件字段）。

### 用到的工具
- `script.characterExtract`：把正文切成条目（页面上对应「资产管理 → 资产表」）。
- `script.characterMerge`：与已有清单合并去重，保留你手工改过的描述。

### 约束与验收
- 只认正文里写出来的事实；没写的一律不编（宁可留空让你补）。
- 人名与别名必须能对上同一张资产图，别出现「林月」和「小月」两条。
- 外观描述里不出现镜头语言（那是分镜的事）。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
