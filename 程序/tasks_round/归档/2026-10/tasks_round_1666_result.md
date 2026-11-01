# R1666 功能轮（文档先行推广）：阶段 13 质检与交付的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k delivery_scope agents_md distribution_selfcheck`：28 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S13 节（共 33 条 REQ：✅27／🟡1／⬜0／❓5），范围说明追加 S13。
- `程序/docs/DESIGN.md`：新增 S13 节（模块分工、DES-S13-xx、测试锚定表）。
- `程序/tests/test_delivery_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。
- 顺带修正 `程序/PROJECT_MAP.md` 阶段 05 行输入：去掉仅有声明、无代码写入的 `storyboard_draft.json`（REQ-S03-43 ❓）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S13-28**（❓）：成果确认清单写入 `commercial_status='pending'`（`stage_completion_service.py:125`），但没有任何代码读取或更新该字段；`commercial_delivery_status()` 除测试外也无调用方…
- **REQ-S13-24**（❓）：`stage_layout` 把 `qc_report.json`、`delivery.json` 登记为本阶段声明产物，`architecture.md` 与阶段模板还写 `delivery_manifest.json`。
- **REQ-S13-25**（❓）：`pipeline-delivery` 的约束写“未通过质检不得标记交付完成”，并声明工具 `delivery.validate`/`delivery.package`。
- **REQ-S13-26**（❓）：完成判定接受 `.mp4/.mov/.mkv`（`stage_completion_service.py:14,16`），导入只允许 `.mp4/.mov`（`delivery_import_service.py:11`）。
- **REQ-S13-27**（🟡）：阶段 12（后期剪辑）与本阶段的成果目录相互读取：后期剪辑的完成判定同时扫描 `交付目录/导出成片`（`stage_completion_service.py:14`）。
- **REQ-S13-52**（❓）：并行配置声明的“三类独立检查＋汇总”与阶段模板 `delivery_process_template.yaml` 的四步（核验交付物→打包→生成报告→写 `delivery_manifest.json`）无对应的程序化动作；只有 `script_structu…

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
- `test_round_baselines.test_round_number_continuous` 待全部阶段合入后由主树补记状态页轮次头转绿（本轮未跑该用例）。
