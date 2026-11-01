# R1658 功能轮（文档先行推广）：阶段 05 资产管理的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k assets_scope agents_md distribution_selfcheck`：29 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S05 节（共 24 条 REQ：✅21／🟡2／⬜0／❓1），范围说明追加 S05。
- `程序/docs/DESIGN.md`：新增 S05 节（模块分工、DES-S05-xx、测试锚定表）。
- `程序/tests/test_assets_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S05-05**（🟡）：`pipeline-assets` SKILL 的 `input` 列了 `characterManifest`／`sceneManifest`／`propManifest`／`sceneBreakdown`／`emotionCurve`，但程序（`asset…
- **REQ-S05-32**（❓）：需拍板（疑似缺陷）：SG-01 读 `资产清单/assets.json` 里的 `image`，但程序登记图片只写图片登记表 `<资产库>/assets.json`（`asset_batch_service.register_image`／`import_as…
- **REQ-S05-42**（🟡）：`asset_contract.panel_text()` 仍写“资产管理页（02_assets）”“06 连贯性清单”，与现行 `05资产管理`、阶段 06 编号不符（代码文案陈旧，未改动）。

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
- `test_round_baselines.test_round_number_continuous` 待全部阶段合入后由主树补记状态页轮次头转绿（本轮未跑该用例）。
