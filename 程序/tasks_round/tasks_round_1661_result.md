# R1661 功能轮（文档先行推广）：阶段 08 首帧管理的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k keyframe_scope agents_md distribution_selfcheck`：25 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S08 节（共 26 条 REQ：✅24／🟡1／⬜0／❓1），范围说明追加 S08。
- `程序/docs/DESIGN.md`：新增 S08 节（模块分工、DES-S08-xx、测试锚定表）。
- `程序/tests/test_keyframe_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S08-40**（❓）：阶段产出清单的名字与位置有三处不一致：`stage_layout` 契约写 `frames.json`；流程模板第 4 步和 `architecture.md` 写 `keyframe_manifest.json`；实际“完成”的依据是已采用分镜 JSON 里…
- **REQ-S08-41**（🟡）：`pipeline-keyframe` SKILL 的 `output` 写 `keyframeManifest`，与 REQ-S08-40 同源；随其决议一并处理。

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
- `test_round_baselines.test_round_number_continuous` 待全部阶段合入后由主树补记状态页轮次头转绿（本轮未跑该用例）。
