# R1656 功能轮（文档先行推广）：阶段 03 初步分镜的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k storyboard_scope agents_md distribution_selfcheck round_baselines`：32 条全过（含新增锚定测试 9 条），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S03 节（共 30 条 REQ：✅25／🟡1／⬜0／❓4），范围说明追加 S03。
- `程序/docs/DESIGN.md`：新增 S03 节（模块分工、DES-S03-xx、测试锚定表）。
- `程序/tests/test_storyboard_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S03-19**（❓）：契约与阶段输出契约都把"通过校验并采用后的 JSON"称为"分镜定稿"，并称其"锁定"来源剧本、编号、镜头编号、时长、台词与连续性约束；但 `pet_bus.STAGES` 的"分镜定稿"是第 07 阶段，且 07 才做批次划分与三元组补全。
- **REQ-S03-20**（❓）：阶段并行提示要求本阶段"生成每个镜头时核对三元组并写入 `batch_id`"（`stage_parallel.py:203`），但批次划分的权威阶段是 07 分镜定稿（SG-03 查 `batch_id`、每批 ≤4 镜且 ≤18 秒，`stage_layo…
- **REQ-S03-43**（❓）：`stage_layout.STAGES` 与 `architecture.md` 声明本阶段产物名为固定的 `storyboard_draft.json`，并作为 04–07 阶段的输入名；实际没有任何代码写这个文件名，产物是模型命名的分镜 JSON（`分镜…
- **REQ-S03-44**（❓）：`script_manifest_schema.PRODUCERS` 把 `scene_breakdown.json` 的产出方登记为本阶段 `storyboard-scene-breakdown` SKILL，其他文档也称之为"五类剧本 manifest"之…
- **REQ-S03-51**（🟡）：`workflow_settings` 的单独"初步分镜"流程默认技能是外部包 `short-drama-storyboard`，与 AIGC 全流程预设里的 `pipeline-storyboard-draft` 并存；两条入口对应哪种用户场景、何者为准，文…

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
