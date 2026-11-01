# R1657 功能轮（文档先行推广）：阶段 04 分镜预演的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k animatic_scope agents_md distribution_selfcheck`：26 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S04 节（共 29 条 REQ：✅25／🟡1／⬜0／❓3），范围说明追加 S04。
- `程序/docs/DESIGN.md`：新增 S04 节（模块分工、DES-S04-xx、测试锚定表）。
- `程序/tests/test_animatic_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S04-52**（🟡）：SKILL 正文"本阶段读取的项目锁"列出 8 项以上锁（赛道、素材来源、分辨率、帧率、视频模型等），并称"必填项缺失记为配置缺口并返回准备阶段"。
- **REQ-S04-60**（❓）：`stage_layout` 声明本阶段输入为固定名 `storyboard_draft.json`、并为 `04分镜预演` 登记了 `animatic_notes.md`（"节奏、时长与对白同步确认记录"），但实际没有任何代码写这两个文件：输入是"已采用分镜…
- **REQ-S04-61**（❓）：预演按 `batch_id` 分批，但批次划分的权威阶段是 07 分镜定稿，03 是否写 `batch_id` 本身也未定（REQ-S03-20）。
- **REQ-S04-62**（❓）：预演的成果（草图、临时声音）不被任何下游阶段读取；资产管理与后续阶段只读 SG-B 的通过结果。

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
