# R3496 结果文件 — 工程文档体系补齐与防腐烂任务书 轮 2：ADR 升级 MADR＋建索引
<!-- round-evidence: {"commit_base": "54f32223", "credential_hits": 0, "evidence_sha256": "092acff1cf1b839e", "exit": 0, "failed": 0, "passed": 10, "round": 3496, "tests": "run_selftests.py -k agent_doc_budget requirement_traceability"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书指定的文档治理轮；本轮纯文档，无产品 `.py` 改动）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`run_selftests.py -k agent_doc_budget requirement_traceability` 10/10 绿；`doc_registry.py` 核对通过（70 份）；`smoke_test.py` 9/9 绿。架构门禁未整轮重跑（无产品代码改动）；全量回归未触发，欠账以 `full-safe-receipts.json` 为准。
3. **欠账少了吗？** 无新增欠账；`docs/adr/` 从单文件孤儿升级为 MADR 框架（README 索引＋TEMPLATE＋6 份 ADR），补上任务书点名的 ADR-0002 缺号腐烂。

## 本轮改动

- 新增 `程序/docs/adr/README.md`：状态枚举（提议／已接受／已废弃／已被替代）、编号规则（4 位递增不复用）、索引表（编号／标题／状态／日期／取代关系）、指向 `TEMPLATE.md`。
- 新增 `程序/docs/adr/TEMPLATE.md`：MADR 精简五段，`考虑过的选项` 为必填段。
- 改写 `程序/docs/adr/0001-layered-architecture.md`：补 `日期：2026-11-15`（与 `git log` 实测 `feafa48e`/R2569 一致）、`层级/阶段`、`取代`字段与 `考 虑过的选项` 段（按 `AGENTS.md` §2.3、`架构变更记录.md`、R2443/R1649 证据重建，原始备选评审注明「历史未记录」）。
- 新增 `0002-whitelist-dependencies.md`（依赖白名单，2026-11-17，证据：引入成熟框架任务书已确认决策＋R3215 `504f53bf`）。
- 新增 `0003-fixed-13-stage-pipeline.md`（13 阶段固定顺序，补记，证据：`architecture.md` §4／`pet_bus.STAGES` 实测 13 项）。
- 新增 `0004-single-authority-ratchet.md`（唯一权威源与棘轮门禁，补记，证据：`AGENTS.md` §2.2／`架构统一基数.json`）。
- 新增 `0005-hidden-desktop-tests.md`（测试隐藏桌面强制执行，2026-11-16，证据：测试隐藏桌面任务书 R3039 已确认决策 15 条）。
- 新增 `0006-round-system-no-external-spec-framework.md`（保留轮次制不引外部 spec 框架，2026-11-19，证据：本任务书 D1／D13／D15）。
- `程序/文档导航.md`：「阶段文档」节补登记整个 `docs/adr/`。
- `程序/说明/工程文档登记表.md`：新增 7 行（README/TEMPLATE/0002–0006），0001 核验轮次升 R3496；`文档登记快照.json` 重新生成（70 份）。

## 与任务书口径的差异说明

- **补记日期口径**：0003／0004／0006 决策早于记录日，ADR `日期` 字段与索引表均标「补记」，决策出处写入各文「背景与问题」；0002 用政策落地提交日 2026-11-17，0005 用任务书拍板日 2026-11-16，0001 用任务书实测的 `feafa48e` 提交日 2026-11-15。
- **0001「考虑过的选项」**：原始分层决策的备选评审记录在 `架构变更记录.md` 中未见（该文件只记迁移结果），按任务书「查不到写历史未记录」口径，选项按现存证据重建并明确标注。
- **无 `未立项` 占位**：任务书允许 0002–0006 中取不到证据的编号留 `未立项`；五条候选全部取得现存证据（任务书已确认决策节／`architecture.md` §4／`AGENTS.md` §2.2＋基数.json／隐藏桌面任务书／本任务书 D1·D13），故 6 份 ADR 全部实写、索引无占位。

## 验收对照（任务书轮 2 勾选）

- [x] `docs/adr/README.md` 含状态枚举、编号规则、索引表、模板指引
- [x] `TEMPLATE.md` 五段齐全，`考虑过的选项` 为必填段
- [x] `0001` 补齐日期与考虑过的选项；日期 2026-11-15 与 `feafa48e` 一致
- [x] 新增 ADR 每份都有 `考虑过的选项` 且非空非套话；索引表与实际文件一一对应（6 行＝6 文件）
- [x] 无证据的编号在索引里显示 `未立项`——本轮无此情形（5/5 候选均有证据），故无占位行
- [x] `文档导航.md` 已登记 `docs/adr/`

## 三个基线数

- 默认冒烟：9/9 绿。
- 架构门禁：未整轮重跑（本轮无产品 `.py` 改动；`agent_doc_budget`＋`requirement_traceability` 定向 10/10 绿）。
- 全量回归：未触发；欠账以 `full-safe-receipts.json` 为准。

## 提交

- 分支 `codex/eng-docs`（工作树 `.agents/worktrees/eng-docs`），轮次 R3496（round_claim 领取；3493–3495 被其他车道占用）。
- commit hash：见提交记录（`dev.py commit` 生成 `tasks_round/evidence/R3496.json`）。
