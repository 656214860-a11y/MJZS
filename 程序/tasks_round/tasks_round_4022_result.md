# R4022 — 文档轮：分发清单补声明《阶段文档写法》，改一处错字（docs-only）
<!-- round-evidence: {"commit_base": "42a35fa5", "credential_hits": 0, "evidence_sha256": "c2f3c9d1b2d7fbe4", "exit": 0, "failed": 0, "passed": 0, "round": 4022, "tests": "docs-only"} -->

## 三问

1. **轮次类型**：文档轮（docs-only）。给 `codex/doc-format` 车道已提交的《阶段文档写法》（R3986，DOC-F0）补上合入前缺的一处声明，不改任何代码。
2. **测试跑了吗、三个基线各是什么结果**：跑了 6 个文档与清单相关的测试文件共 45 条，全过（命令见下）。默认冒烟、架构门禁在合入时由出口 CI 跑；全量未跑（文档轮不要求）。
3. **欠账少了吗**：少了一条将要发生的红——不补这处声明，合入后主干全量的 `test_distribution_selfcheck.test_manifest_covers_every_file` 会红（R3989 新增《用户沟通与要求标准》时出过同样的问题，R4014 修掉）。DOC-G1 的结构守卫仍未入库，见「没做的」。

## 改了什么

| 文件 | 改动 |
|---|---|
| `distribution_manifest.md` | 「必须排除」表「开发文档」一行补上 `程序/docs/process/阶段文档写法.md` |
| `docs/process/阶段文档写法.md` | 「写法约束」第 2 条错字：「不重抱一遍」改成「不重抄一遍」 |

## 验证

工作目录 `程序`，`PYTHONPATH` 含 `tests` 和当前目录：

`python -X utf8 -B -m unittest tests.test_distribution_selfcheck tests.architecture.test_agent_doc_budget tests.architecture.test_doc_registry_migration tests.architecture.test_requirement_traceability tests.test_root_layout tests.test_copy_rules`

结果：`Ran 45 tests`，`OK`。

## 审查结论（《阶段文档写法》，R3986）

主控通读一遍：位置、两节各四个小节的表头和编号段、状态记号、样例、写法约束、「事实从哪来」五条齐全，没有和现有规范冲突的地方；除上面一处错字外不需要改。

## 没做的

- DOC-G1 的结构守卫 `tests/architecture/test_stage_doc_sections.py` 仍在本车道的 `git stash` 里（见 R4004 失败报告）。它要在 `governance/structure.json` 登记，登记后必须重写 `governance/structure-baseline.json`，而这个文件和活跃车道 `codex/l2-maturity-takeover` 必然冲突。等那条车道合入或失活（2026-11-22 01:03 之后）再放出来、重写基线、提交。
- 守卫入库之前不开 13 个阶段文件的细化车道（那些任务卡的验收命令要用这个守卫）。
