# R3503 结果文件 — 工程文档体系补齐与防腐烂任务书 轮 5：收口（导航同步＋链接校验扩展＋登记表全量校验）
<!-- round-evidence: {"commit_base": "44f234f8", "credential_hits": 0, "evidence_sha256": "f465d3f3dc6b2e1c", "exit": 0, "failed": 0, "passed": 13, "round": 3503, "tests": "run_selftests.py -k agent_doc_budget requirement_traceability"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书指定的文档治理收口轮；文档＋架构门禁测试本体扩展，无产品运行时代码改动）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`run_selftests.py -k agent_doc_budget requirement_traceability` 13/13 绿（`agent_doc_budget` 8 条、`requirement_traceability` 5 条）；`smoke_test.py --architecture` 全量 545 条：542 绿、2 红 1 错，红集全部为环境性/结构性欠账（详见下），本轮改动文件 8/8 全绿、零新增红。默认冒烟未单独重跑（本轮未改 AGENTS.md 规则正文、无活跃逻辑改动；架构门禁已覆盖文档预算断言）。全量回归未触发，欠账以 `full-safe-receipts.json` 为准。
3. **欠账少了吗？** 无新增欠账；`文档导航.md` 两条死链修复、四处路径口径落为可校验链接；`test_agent_doc_budget.py` 从 3 文件预算扩到 9 文件＋两条 D10 总量断言＋负向自测，登记表防死表能力落地（任务书遗留项「登记表变死表」由本轮反向断言部分缓解，② 的门禁挂载仍属后续册）。

## 本轮改动

- `程序/文档导航.md`：
  - L20–L21 路径口径修正：`使用说明.md`／`使用说明.txt` 实际在**仓库根**（`程序/` 之外），改为 markdown 链接 `[使用说明.md](../使用说明.md)`／`[使用说明.txt](../使用说明.txt)`，路径由 `broken_links()` 实测可验。
  - 死链修复：`crud_audit_20260926.md`、`HANDOFF_20261022_1830.md` 两行原为裸文件名（解析到 `程序/` 下不存在），改为指向实际归档实体 `tasks_round/归档/2026-11_历史文档/` 下同名文件的 markdown 链接。
- `程序/tests/architecture/test_agent_doc_budget.py` 扩展：
  - `BUDGETS` 由 3 项增至 9 项，新增 `文档导航.md`、`说明/工程文档登记表.md`、`说明/产品需求规格.md`、`说明/已知坑与不可破坏契约.md`、`维护记录/README.md`、`docs/adr/README.md`，预算统一 16000 字节（沿用文件 docstring 的 16 KB 加载窗口依据）。
  - 新增 `test_program_root_markdown_count_within_budget`：`程序/` 根 `.md` 实测 **18** ≤ 预算 18（D10，零余量——新增根级 md 将直接转红）。
  - 新增 `test_maintenance_record_top_level_count_within_budget`：`维护记录/` 顶层文件实测 **57**（全部文件，含 .py/.json）≤ 预算 60。
  - 新增 `test_budget_guard_rejects_oversize_sample`：临时目录构造 20000 字节样本，断言 `oversize()` 检出超预算——证明体积断言会红而非恒真。
  - 未并入默认冒烟：本文件属 `tests/architecture/`，只经 `--architecture` 门禁与 `-k` 定向触发（D12）。
- `程序/说明/工程文档登记表.md`：`文档导航.md` 行核验轮次 R3490→R3503；快照 `维护记录/文档登记快照.json` 重生成，71 份双向一致。

## 漏登记项核对（任务书轮 5 第 2 条）

任务书列的六类「漏登记」经逐项核对**在轮 0 登记表建立时已全覆盖**（登记表按文件系统双向扫描生成，非手工枚举）：

| 类别 | 任务书口径 | 实测 | 登记位置 |
| --- | --- | --- | --- |
| `SECURITY.md`/`GLOSSARY.md`/`CHANGELOG.md`/`distribution_manifest.md` | 漏登记 | 均已登记（R3490 行 15/16/19/23） | 登记表根级区 |
| `docs/adr/` | 漏登记 | 8 份全登记（0001–0006＋README＋TEMPLATE，R3496） | 登记表 docs 区 |
| `说明/` 19 份 | 漏登记 | 实测 **20** 份（R3499 新增已知坑文档后），全登记 | 登记表说明区 |
| `docs/review/` 非四页 | 9 份 | 实测 **7** 份（README＋6 份任务书/方案/棘轮），11 份全登记 | 登记表 docs 区 |

登记表由 `doc_registry.py --check` 双向核对（存在未登记/登记缺失均报错），「漏登记」在机制上已不可能静默发生；任务书数字为立书时旧快照，以实测为准。

## 架构门禁红集定性（545 条：542 绿 / 2 红 / 1 错）

| 测试 | 结果 | 定性 |
| --- | --- | --- |
| `test_round_baselines.test_round_number_continuous` | FAIL 3480≠3500 | **结构性**：`project_status.md` 按 runbook §「分支记录只写结果文件，合入 master 后单独补记状态页」仅 master 可写；分支结果文件推进后该断言在分支上必红，合入时由状态页同步轮消解（R3459 合并轮同款记录在案）。 |
| `test_agents_md.test_performance_history_is_declared_as_historical_only` | ERROR | **环境性**：`维护记录/基准历史.json` 为 gitignored 运行时文件，主工作树存在、本工作树无；与本轮 diff 无关。 |
| `test_skill_reference_injection.test_script_stages_name_only_their_approved_00_references` | FAIL | **环境性**：`程序/skills/00全流程SKILL/AIGC创作全流程` 为 gitlink 子模块（mode 160000），本工作树未初始化子模块内容；主工作树文件存在。与 `优化待办队列.md` UI-U7-4 记录的 `dsh-*` 工作树环境性红同类。 |

本轮改动文件（`test_agent_doc_budget.py` 8 条、文档链接断言）在门禁内全绿；红集与改前基线一致，无新增红。

## 验收对照（任务书轮 5 勾选）

- [x] `文档导航.md` 无死链（`broken_links()` 返回空；两条修复链接改为 markdown 链接由断言实测）
- [x] 六类漏登记项全部登记（核对结果：轮 0 已全覆盖，见上表）
- [x] `test_agent_doc_budget.py` 覆盖 9 个文件（3→9），含两条预算断言与负向自测
- [x] `程序/` 根 md 数 18 ≤ 18、`维护记录/` 顶层 57 ≤ 60（实测报告数值）
- [x] 定向测试全绿：`run_selftests.py -k agent_doc_budget requirement_traceability` 13/13
- [x] 架构门禁通过口径：红集与改前基线一致（3 项均为结构性/环境性既有欠账，本轮零新增红）

## 三个基线数

- 默认冒烟：未单独重跑（本轮未改 AGENTS.md；最近一次 R3499 轮 9/9 绿）。
- 架构门禁：当轮实际 545 条，542 绿 / 2 红 / 1 错，红集定性如上（结构性 1＋环境性 2，零新增）。
- 全量回归：未触发；欠账以 `full-safe-receipts.json` 为准。

## 遗留（如实记录）

- 「登记表变死表」风险：本轮反向断言（根 md≤18、维护记录≤60、9 文件体积预算）已把失控面收窄，但登记表仍需后续册的门禁挂载才能根治——任务书 §6 已预先声明本册无法根治，记为本册遗留。
- `项目状态页轮次头`在分支上保持 3480 属协议内状态，合入 master 后由状态页同步补记。

## 提交

- 分支 `codex/eng-docs`（工作树 `.agents/worktrees/eng-docs`），轮次 R3503（round_claim 领取；3500–3502 被其他车道占用）。
- commit hash：见提交记录（`dev.py commit` 生成 `tasks_round/evidence/R3503.json`）。
