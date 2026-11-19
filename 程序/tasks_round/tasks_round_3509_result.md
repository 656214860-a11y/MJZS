# R3509 结果文件 — 合并预演发现的环境性误伤修复：D10 计数改 git 跟踪口径
<!-- round-evidence: {"commit_base": "5e15e7cd", "credential_hits": 0, "evidence_sha256": "fb51e22945f6116e", "exit": 0, "failed": 0, "passed": 8, "round": 3509, "tests": "run_selftests.py -k agent_doc_budget"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（合并门禁 CI 在主工作树实测红：R3503 新增的两条计数断言按文件系统枚举，把主工作树独有的 gitignored 运行时状态文件计入预算——工作树 57、主树合并后 61 > 60）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`run_selftests.py -k agent_doc_budget` 8/8 绿；`smoke_test.py --architecture` 未整轮重跑（改动仅限该测试文件内部实现，定向已覆盖；合并轮 CI 会在主树全量复验）。默认冒烟未跑（无产品逻辑改动）；全量回归未触发，欠账以 `full-safe-receipts.json` 为准。
3. **欠账少了吗？** 无新增欠账；消除一处「同断言在不同工作树给出不同结论」的环境性假红——D10 预算本意是约束**入库文件**膨胀，运行时落盘的 gitignored 状态文件不应计入。

## 本轮改动

- `程序/tests/architecture/test_agent_doc_budget.py`：
  - 新增 `tracked_files()`：以 `git ls-files -z`（cwd=`程序/`）取版本库跟踪文件集，git 不可用时退回 `rglob` 文件系统枚举；docstring 注明口径理由。
  - `test_program_root_markdown_count_within_budget` 与 `test_maintenance_record_top_level_count_within_budget` 改用跟踪文件口径：主树实测根 .md **18**、维护记录/ 顶层跟踪文件 **55**（合并后 57）≤ 60；工作树实测同值——两环境结论一致。
  - 断言文案同步为「跟踪文件」口径。

## 误伤定性

- 主工作树 `维护记录/` 顶层文件系统实有 59 个，其中 4 个是 gitignored 运行时状态（`上次关闭清理.json`、`任务队列.json`、`基准历史.json`、`自检增量.json`）；合并后工作树文件系统数 61 触发预算。跟踪口径下两侧均为 55→57，预算语义不变、判定确定。
- 同轮合并 CI 另报 `test_real_repo_state_is_clean` 孤儿完成文件——属预期时序问题：任务书尚未入库 master，合并前先以独立提交补入 `程序/tasks_round/工程文档体系补齐与防腐烂任务书.md`（内容与 brass-flywheel 快照逐字节一致）后消解，非本测试缺陷。

## 验收对照

- [x] 计数断言与运行时环境解耦（git 跟踪口径，gitignore 状态文件不计入）
- [x] 两环境实测一致：工作树 55/18、主树合并后 57/18，均 ≤ 预算
- [x] `agent_doc_budget` 8/8 绿，负向自测仍在
- [x] 未削弱断言语义（预算值不变、覆盖文件数不变）

## 三个基线数

- 默认冒烟：未跑（测试文件内部实现改动，定向覆盖）。
- 架构门禁：定向 `agent_doc_budget` 8/8 绿；全量以合并轮 CI 为准。
- 全量回归：未触发；欠账以 `full-safe-receipts.json` 为准。

## 提交

- 分支 `codex/eng-docs`，轮次 R3509（round_claim 领取；3504–3508 被其他车道占用）。
- commit hash：见提交记录（`dev.py commit` 生成 `tasks_round/evidence/R3509.json`）。
