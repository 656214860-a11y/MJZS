# R1655 功能轮（文档先行推广）：阶段 02 剧本结构的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k script_structure agents_md distribution_selfcheck round_baselines`：新测试 6/6、`test_script_structure` 23/23、`test_distribution_selfcheck` 3/3 通过；`test_agents_md` 仅 `test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在，非本轮引入，主树绿）。未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S02 节（REQ-S02-01~03、10~15、20~25、30~31 与非目标），范围说明更新为已覆盖 S01、S02。
- `程序/docs/DESIGN.md`：新增 S02 节（模块分工、DES-S02-xx、测试锚定表）。
- `程序/tests/test_script_structure_scope.py`（新增 6 条）：锚定 REQ-S02-02/15/23（归属部分）/30/31。
- `程序/architecture.md`：纠正结构稿目录（`02剧本结构/结构剧本/`，原写 `docs/` 与代码不符）；剧本结构行的输入改为“被采用自然剧本”，manifest 是否必须产出标注待定。
- `程序/PROJECT_MAP.md`：阶段 02 输入由“剧本原稿、创意简报”改为“被采用的自然剧本”（创意简报不进 02，与 S01 文档一致）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓）

- **REQ-S02-23**：`character_manifest`／`scene_manifest`／`prop_manifest` 归 02，但默认本地规则路径不写，只有模型执行 `script-character-extraction` 时才可能落盘，程序不核验，下游也没有消费它们的代码。要不要要求 02 必须产出并核验？
- **REQ-S02-25**：`PRODUCERS` 登记的落盘目录仍是旧名 `00_script`，与 02 新写目录 `02剧本结构` 不一致。是否迁移？

## D 未做与局限

- `stage_parallel.py` 第 48~53 行注释仍含“01 剧本：角色/场景/道具提取依赖链”旧说法，属代码注释，本轮不动。
- `project_status.md:219` 的旧断言记录属历史，未改。
- 既有 `test_script_structure` 等用例未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- AGENTS.md 中是否还有 02 专属条款：本轮检索未发现需迁出的条款。
