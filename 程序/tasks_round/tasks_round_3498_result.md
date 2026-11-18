# R3498 结果文件 — 工程文档体系补齐与防腐烂任务书 轮 3：维护记录/ 建立索引
<!-- round-evidence: {"commit_base": "2124e7e7", "credential_hits": 0, "evidence_sha256": "0844c0e9e86324a3", "exit": 0, "failed": 0, "passed": 10, "round": 3498, "tests": "run_selftests.py -k agent_doc_budget requirement_traceability"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书指定的文档治理轮；本轮纯文档，无产品 `.py` 改动）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`run_selftests.py -k agent_doc_budget requirement_traceability` 10/10 绿；`smoke_test.py` 9/9 绿；集合相等脚本实测 57＝57。架构门禁未整轮重跑（无产品代码改动）；全量回归未触发，欠账以 `full-safe-receipts.json` 为准。
3. **欠账少了吗？** 无新增欠账；`维护记录/` 56 份顶层文件首次有全量索引，四类分区落地。

## 本轮改动

- 新增 `程序/维护记录/README.md`：Diátaxis 近似四格分区——一类·当前有效基线 18 条（门禁读取 JSON＋政策/口径文档）、二类·审计快照 14 条、三类·路线图与待办 8 条（含 `claim_queue.py` 兼容脚本，标注非文档）、四类·归档 16 条（状态历史归档、架构变更记录、期交付物等）；每条含「一句话用途｜是否当前有效｜谁读」；两个子目录按整体说明。
- `程序/文档导航.md`：「历史与台账」节 `维护记录/` 行改为指向 `维护记录/README.md` 四类索引。

## 与任务书口径的差异说明

- **顶层文件数**：任务书写「59 份／归档/ 子目录 4」，本工作树实测顶层 **56 份**（加本索引后 57）、子目录仅 `代码腐烂审计/`、`基准脚本/` 两个，**无 `维护记录/归档/`**（`tasks_round/归档` 在目录外）。索引按实测集合全覆盖，README 末尾注明差异。
- **分类取舍**：`缺陷台账_20261001.md` 按任务书归二类（一次性普查），但注明其 A 级挂账仍被 `联调测试出口基线.md` §4 活引用；`claim_queue.py` 非文档，归三类并标注「维护脚本」；`README.md` 自身列一类末行以满足集合相等。
- **CODE-ROT-REPORT.md**：任务书二类示例提及，但顶层不存在（在 `代码腐烂审计/` 工作区内），不单列。

## 验收对照（任务书轮 3 勾选）

- [x] `维护记录/README.md` 存在，四类分区齐全
- [x] 顶层文件逐条登记，`Get-ChildItem` 集合与登记条目相等（实测 57＝57，脚本核对 missing/extra 均空）
- [x] 每个子目录有一行整体说明（`代码腐烂审计/`、`基准脚本/`）
- [x] `文档导航.md` 维护记录行已改为指向本 README

## 三个基线数

- 默认冒烟：9/9 绿。
- 架构门禁：未整轮重跑（本轮无产品 `.py` 改动；`agent_doc_budget`＋`requirement_traceability` 定向 10/10 绿）。
- 全量回归：未触发；欠账以 `full-safe-receipts.json` 为准。

## 提交

- 分支 `codex/eng-docs`（工作树 `.agents/worktrees/eng-docs`），轮次 R3498（round_claim 领取；3497 被其他车道占用）。
- commit hash：见提交记录（`dev.py commit` 生成 `tasks_round/evidence/R3498.json`）。
