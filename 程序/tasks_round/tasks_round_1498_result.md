# R1498 车道 B：阶段 SKILL 审核与适配
- 本轮类型：兼容轮（SKILL 内容审核与适配）。
- 校验跑了吗：health = []；验收修复后按用户指定的直接 unittest 命令通过 195 项（53.305s，OK）；未跑全量或 smoke gate。
- 欠账变化：补齐 7 份适配、修正 4 份小 SKILL；新增登记章节内联实现缺口，旧页面编号和外部包冲突保留。

## 审核发现（07—13 为对应阶段目录，文件均在 程序/skills；逐份共 42 份）
| 文件 | 问题 → 处理 |
|---|---|
| 07/pipeline-storyboard-final.skill.md | 缺新版分镜/闸门及读锁声明；D 锁措辞易误作本阶段选锁 → 已改 |
| 07/storyboard-asset-sync.skill.md | 无条件要求实体图片，与 M0/M1 冲突 → 已改；旧页面编号仅记录 |
| 07/storyboard-consistency-lock.skill.md | 未见确定的新版语义冲突 → 仅记录保留 |
| 07/storyboard-final-validate.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 07/storyboard-prompt-render.skill.md | 未见确定的新版语义冲突 → 仅记录保留 |
| 07/storyboard-version-snapshot.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 08/firstframe-auto-fill.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 08/firstframe-batch.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 08/firstframe-quality.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 08/firstframe-retry.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 08/firstframe-thumbnail.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 08/pipeline-keyframe.skill.md | 缺故事板/M2/出图授权边界和读锁声明 → 已改 |
| 09/pipeline-previs.skill.md | 缺新引擎引用/读锁声明；实际无 PREVIS 专节 → 已改为戏型检查依据 |
| 09/whitemodel-actor-place.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 09/whitemodel-camera-record.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 09/whitemodel-motion-preview.skill.md | “正式出首帧之前”与当前阶段顺序不一致 → 仅记录，未改业务顺序 |
| 09/whitemodel-rhythm-check.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 09/whitemodel-scene-build.skill.md | 未见确定的新版语义冲突 → 仅记录保留 |
| 10/pipeline-video-generation.skill.md | 缺投喂/模型章节和读锁声明；“无本地 adapter”过时 → 已改 |
| 10/video-batch-submit.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 10/video-multi-model-route.skill.md | 自动分派模型可能覆盖版本锁 → 已改；旧页面编号仅记录 |
| 10/video-quality-check.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 10/video-retry.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 11/pipeline-audio-subtitle.skill.md | 缺声音模板/方言条件引用及读锁声明 → 已改 |
| 11/subtitle-auto-align.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 11/subtitle-format-export.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 11/voice-emotion-check.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 11/voice-multi-character.skill.md | 历史兼容 ID 已指向 TTS，无需重复实现 → 仅记录保留 |
| 11/voice-tts-synthesis.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 12/edit-auto-compose.skill.md | 未见确定的新版语义冲突 → 仅记录保留 |
| 12/edit-bgm-sfx.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 12/edit-multi-format-export.skill.md | 平台示例规格可能覆盖项目交付锁 → 已改 |
| 12/edit-preview-generate.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 12/edit-transition-library.skill.md | 无条件默认硬切可能覆盖 splice_mode → 已改；旧页面编号仅记录 |
| 12/pipeline-editing.skill.md | 缺新版转场检查/读锁声明 → 已改 |
| 12/video-audio-sync-precheck.skill.md | 未见确定的新版语义冲突 → 仅记录保留 |
| 13/delivery-archive.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 13/delivery-report-generate.skill.md | 未见确定的新版语义冲突 → 仅记录保留 |
| 13/pipeline-delivery.skill.md | 缺新版 QC/读锁声明；稿件机检不可替代成片检查 → 已改 |
| 13/qa-compliance-check.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 13/qa-overall-check.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 13/qa-style-consistency.skill.md | 未见确定的新版语义冲突 → 仅记录保留；旧页面编号仅记录 |
| 09/create-blender-story-video/SKILL.md（外部入口） | 固定 9:16/4K/30fps、再次确认风格、默认生成参考图与无人值守项目锁/提示词默认有冲突；链接存在 → 仅审不改 |

## 改动与冲突替换
- 7 份 pipeline：新增带锚点的新包章节引用及全部项目锁键；直接读取、不弹问；选填默认写入交付，必填缺失退回配置；保留调试/人工复核/总控替换。
- 07 pipeline：恢复原句“D 锁只在本阶段放行”及其完整段缝门控；读取已填 splice_mode 的新增说明另起一段，二者无冲突。
- 10 pipeline：旧句“尚无本地权威 adapter”与新版 AIGC创作全流程/short-drama-director/references/model-adapters.md 已存在冲突；保留新包说明另起一段，恢复专有语法及“2.0 禁首尾帧”未经控制面或实际接口核验时“不能作为已验证规则写入本阶段”的限制。测试期望未修改、未弱化。
- storyboard-asset-sync：替换无条件“还得有图/查有没有图”，按 M0 文字、M1 接线单、M2 实图分流，避免阻断合法文本产物。
- video-multi-model-route：替换任意按档换模型；路由/fallback 限于项目版本锁，不重问锁；预算确认仍保留。
- edit-multi-format-export：替换平台示例直接套规格，先读项目规格；额外平台版本另存且不反写主锁。
- edit-transition-library：替换两处“默认硬切”，继承 splice_mode 和已采用段缝方案，避免覆盖 D 锁。
- 映射校正：09 三引擎无 PREVIS 专节，引用各自工作流程作预演检查；13 QC 机检是稿件检查，补充真实媒体验收边界。原功能说明及 frontmatter 其余保留，未复制大段包正文。

## 实际内联体量（_inline_skill_report(strict=True)，UTF-8；上限按字符而非字节）
| 适配文件 | 字节 | 字符 / 300000 |
|---|---:|---:|
| pipeline-storyboard-final.skill.md | 210136 | 167549 |
| pipeline-keyframe.skill.md | 141225 | 106278 |
| pipeline-previs.skill.md | 112801 | 90958 |
| pipeline-video-generation.skill.md | 245659 | 176965 |
| pipeline-audio-subtitle.skill.md | 78428 | 53448 |
| pipeline-editing.skill.md | 98253 | 80576 |
| pipeline-delivery.skill.md | 150034 | 139025 |

## 校验与未完成项
- 指定 health = []；42 份阶段文件及外部入口的 79 个直接 Markdown 引用目标/锚点均可定位；范围与 frontmatter 检查通过；git diff --check 通过。
- 验收复测（程序目录，PYTHONPATH=tests）：../../../运行环境/Python/python.exe -B -m unittest test_master_skill test_skills test_stage_prompt_governance test_workflow_writing_stages architecture.test_skill_reference_injection；输出：Ran 195 tests in 53.305s / OK，exit 0。此前 run_selftests.py 中止不作为通过证据。
- 实现缺口（本轮禁改 Python）：workflow_settings.py:714 起按路径去重并内联整个直接引用文件，忽略 fragment；789 的体检只控制字符上限，不能证明“只注入引用章节”。以上体量均按真实行为计，不冒称章节裁剪已实现。
- 保留事项：27 份小 SKILL 的旧页面编号/阶段时序提示仅记录，待核实 UI 后迁移；外部整包不改；新锁字段 UI/持久化属于 R1483，本轮只声明读取契约，未验证跨车道集成。本次两条合同失败已解决；章节裁剪实现及上述遗留项仍未解决，超出本次修复范围。
- 复测原因与范围：此前改写误删既有功能性门控；本次只修 07/10 两份 pipeline 及本结果文件。两条测试要求的全部片段（含 03、08 keyframe、09 previs）均由指定套件验证通过；首帧/预演无需改动。
