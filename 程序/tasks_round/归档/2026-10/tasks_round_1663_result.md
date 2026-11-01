# R1663 功能轮（文档先行推广）：阶段 10 视频生成的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k video_generation_scope agents_md distribution_selfcheck`：37 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S10 节（共 24 条 REQ：✅19／🟡3／⬜0／❓2），范围说明追加 S10。
- `程序/docs/DESIGN.md`：新增 S10 节（模块分工、DES-S10-xx、测试锚定表）。
- `程序/tests/test_video_generation_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S10-03**（🟡）：流程依赖表 `DEPENDS['video']` 只登记 `('keyframe',)`；而 SKILL `pipeline-video-generation` 写 `dependsOn: [pipeline-previs]`。
- **REQ-S10-18**（🟡）：本地与云端“自动验收”读取的开关来源不同：云端读项目设置 `project_settings.auto_review`，本地读 `pet_ui.should_auto_run(..., 'auto_review')`。
- **REQ-S10-21**（❓）：阶段目录契约和架构文档声明本阶段产出 `videos.json`／`video_manifest.json`，SKILL 也写 `videoManifest`，但代码里没有任何位置写出这两个文件；现行真实成果索引是 `data/state.json` 与各版本…
- **REQ-S10-31**（❓）：`video-batch-submit` 约束写“视频 100 镜/项目”，代码中不存在该上限（`stage_parallel`、`engine` 均无）。
- **REQ-S10-32**（🟡）：SKILL 文字与现状不一致：5 个 SKILL 的“页面位置”仍写“08 视频生成”（真实是第 10 阶段）；`video.batchSubmit`／`retry`／`pause`／`resume` 登记为“只能在页面上按”的步骤，不是可由模型直接执行的工具…

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
- `test_round_baselines.test_round_number_continuous` 待全部阶段合入后由主树补记状态页轮次头转绿（本轮未跑该用例）。
