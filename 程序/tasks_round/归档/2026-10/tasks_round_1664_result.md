# R1664 功能轮（文档先行推广）：阶段 11 配音与字幕的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k audio_subtitle_scope agents_md distribution_selfcheck`：34 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S11 节（共 18 条 REQ：✅13／🟡2／⬜1／❓2），范围说明追加 S11。
- `程序/docs/DESIGN.md`：新增 S11 节（模块分工、DES-S11-xx、测试锚定表）。
- `程序/tests/test_audio_subtitle_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S11-13**（🟡）：音色按稳定角色 ID 优先、显示名其次、再退默认音色（`voice_for`）；`tests/test_audio_role_binding.py` 覆盖绑定，未覆盖“一角一音色、与年龄性别相符”（SKILL 约束，属人工判断，程序不核验）。
- **REQ-S11-24**（❓）：ASS 导出：`subtitle-auto-align`／`subtitle-format-export` 两个 SKILL 承诺 SRT＋ASS（含样式，`subtitle.exportAss`），`architecture.md` 原文同写；代码只有 SR…
- **REQ-S11-40**（❓）：三处对产出的说法互不一致，且没有一处有程序产出方：`stage_layout` 声明 `voice.json`＋`subtitles.json`（后期剪辑阶段声明读取它们），`architecture.md` 原写 `audio_manifest.json`，…
- **REQ-S11-32**（🟡）：`workflow_settings.DEFAULT_SKILLS['audio']` 为空串，旧工作流入口 `FLOWS['audio']` 的默认 SKILL 为空，而阶段级默认勾选为 `pipeline-audio-subtitle`；两条路径并存，未见…

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
- `test_round_baselines.test_round_number_continuous` 待全部阶段合入后由主树补记状态页轮次头转绿（本轮未跑该用例）。
