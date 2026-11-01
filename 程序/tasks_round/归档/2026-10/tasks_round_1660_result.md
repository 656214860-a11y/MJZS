# R1660 功能轮（文档先行推广）：阶段 07 分镜定稿的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k storyboard_final_scope agents_md distribution_selfcheck`：35 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S07 节（共 31 条 REQ：✅24／🟡6／⬜0／❓1），范围说明追加 S07。
- `程序/docs/DESIGN.md`：新增 S07 节（模块分工、DES-S07-xx、测试锚定表）。
- `程序/tests/test_storyboard_final_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S07-03**（🟡）：阶段依赖表 `stage_flow.DEPENDS['final']=('storyboard',)`（`stage_flow.py:62`），不含 `continuity`／`assets`；连贯性与资产的前置只由 SG-01／SG-02 门禁表达。
- **REQ-S07-15**（🟡）：`finalize` 对批次划分异常整体吞掉（`try/except Exception` + `app_logging.swallowed`，`storyboard_final.py:85-89`）：切批失败时仍继续发布无 `batch_id` 的定稿，之后…
- **REQ-S07-43**（🟡）：`stage_layout.STAGES` 为本阶段声明的产出是 `storyboard_final.json`（`stage_layout.py:49-50`；`README.md:1412` 同），实际产出是 `episode.json` + `asset…
- **REQ-S07-44**（🟡）：`stage_layout` 声明 `07分镜定稿/docs/` 下有 `batch_plan.md`（批次划分说明）与 `shot_table.md`（镜头表）（`stage_layout.py:136,370`），但全仓没有任何代码生成这两份文件；`arc…
- **REQ-S07-45**（🟡）：SG-02 门禁报告的 artifacts 路径写成旧式 `<项目>/03_continuity/output/continuity_ledger.json`（`stage_parallel.py:751`），而实际读取走 `read_file(project…
- **REQ-S07-52**（❓）：两条定稿路径并存、口径不同。
- **REQ-S07-53**（🟡）：SKILL `storyboard-version-snapshot`（“可回滚可对比”）声明了 `storyboard.save` 等 tools，程序里没有对应的“版本快照／回滚”实现；`architecture.md:79` 把“输出提示词和快照”列为本…

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
- `test_round_baselines.test_round_number_continuous` 待全部阶段合入后由主树补记状态页轮次头转绿（本轮未跑该用例）。
