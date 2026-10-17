# R1665 功能轮（文档先行推广）：阶段 12 后期剪辑的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k editing_scope agents_md distribution_selfcheck`：30 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S12 节（共 27 条 REQ：✅20／🟡3／⬜0／❓4），范围说明追加 S12。
- `程序/docs/DESIGN.md`：新增 S12 节（模块分工、DES-S12-xx、测试锚定表）。
- `程序/tests/test_editing_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S12-04**（❓）：阶段依赖口径不一致：SKILL `pipeline-editing` 声明依赖音频流水线、输入 `audioTracks／subtitles／audioManifest`，但 `DEPENDS['edit']` 只有 `video`，拼装代码也不读 S11 产…
- **REQ-S12-15**（🟡）：交接包选版口径与成片不一致：交接包取 `(approved or vs)[-1]`（`desktop_media_pages.py:904-905`），不看 `pinned`、不核文件摘要，且没有任何已验收版本时退回最新未验收版；而代码注释声称“与自动粗剪取同…
- **REQ-S12-24**（🟡）：确认只校验“所选文件在 `12后期剪辑/`（含旧 `11后期剪辑`）或 `13质检交付/导出成片/` 下、扩展名为 mp4／mov／mkv、技术合格”，不要求它就是 `edit_bundle.json` 登记的 `MASTER.mp4`，也不核对与 bundl…
- **REQ-S12-25**（❓）：契约与实际产物不符：`stage_layout.STAGES` 为本阶段声明输入 `videos.json／voice.json／subtitles.json`、输出 `edits.json`，且把 `edits.json` 列为 S13 的输入；全库没有任何…
- **REQ-S12-32**（❓）：`edit.exportDouyin／Bilibili／YouTube／Custom`（SKILL `edit-multi-format-export`）只返回平台规格并记账，提示“转码在后期页面上按对应平台的导出按钮执行”，但后期页没有任何平台导出按钮，全库…
- **REQ-S12-33**（❓）：另外 5 个 SKILL（`edit-auto-compose` 声称“自动合成视频片段、添加转场、音效、背景音乐”，`edit-bgm-sfx`、`edit-transition-library`、`edit-preview-generate`、`video…
- **REQ-S12-34**（🟡）：`pipeline-editing` 要求 `editManifest` “逐段保留源视频、音轨、字幕、时间码和修复／切换依据”，实际 `edit_manifest.json` 每镜只有 `shot／version／sha256／source`（`engine…

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
- `test_round_baselines.test_round_number_continuous` 待全部阶段合入后由主树补记状态页轮次头转绿（本轮未跑该用例）。
