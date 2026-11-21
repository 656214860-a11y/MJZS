# R4014 结果：会话接续记录入库，补分发清单声明（修主干全量 1 条红）
<!-- round-evidence: {"commit_base": "9e8b95b1", "credential_hits": 0, "evidence_sha256": "f31b4be9c1b33b5a", "exit": 0, "failed": 0, "passed": 0, "round": 4014, "tests": "docs-only"} -->

## 1. 三问

- 轮次类型：文档轮。新增一份记录文档，改五份文档各一处，没有改任何 `.py`、`.pyw`。
- 测试跑了吗、三个基线过了吗：docs-only。本轮跑了七个文档、目录与分发清单的检查文件：`python -B -m unittest tests.architecture.test_agent_doc_budget tests.architecture.test_doc_registry_migration tests.architecture.test_lane_flow_gates tests.test_root_layout tests.test_dev_entry tests.test_distribution_selfcheck tests.test_copy_rules`，47 条通过，退出码 0。默认冒烟和架构门禁全套由合入检查给出；全量未跑。
- 欠账少了吗：少了 1 条。主干后台全量里 `test_distribution_selfcheck` 的持续红已修（见 §3）。新记 1 条没查明根因的偶发红（`test_round_claim`，见 §4）。

## 2. 产出

1. `docs/records/会话接续记录.md`（新增）：用途、和其他文档的分工、维护办法，以及两个会话各一节（前缀 c2cb0ad3、6c3dd20b）。后一节写到 2026-11-21 08:20：目标、已定的决定、已合入主干的 14 个轮次、等合入的 7 条分支、卡住的 4 张卡和解法、等用户确认的 10 个问题、下一步、派单和合入的办法、欠账。只写去标识的摘要。
2. `runbook.md` §14：加一段「会话上下文的保存」。用户在本次会话里同意过：只存去标识的摘要、新建这份记录、规则写进运行手册 §14。
3. `docs/records/工程文档登记表.md`：表末尾登记这份记录。
4. `docs/records/对话需求追溯.md`：「每个结束的会话把上下文存进工程文档」那一行的落点列补上这份记录和运行手册 §14。没有在表末加行，避开和 `codex/doc-topic-volumes` 在同一位置的改动。
5. 仓库根目录 `AGENTS.md`、`CLAUDE.md`：各加一行，指向这份记录（改后 1132／2000 字节、3027／4000 字节）。
6. `distribution_manifest.md`：在「必须排除」表里列代理协议和架构文档的那一行（分类「开发文档」）补 `程序/docs/process/用户沟通与要求标准.md`（不随包）。没有加在列其他流程文档的「开发流程」那一行：第一次提交时门禁拒绝，那一行和活跃分支 `codex/retire-builtin-prerequisite` 的改动试合并有真实冲突，所以错开了位置。

## 3. 修掉的红：改前的失败输出

主干后台全量 2026-11-21 03:54 在提交 `c1978d68`（R3997）上红，日志 `logs/auto_full_safe.log`：「共 9533 条用例，1429.4 秒；2 个文件有红」。其中一个：

```
test_manifest_covers_every_file (test_distribution_selfcheck.DistributionSelfCheckTests)
AssertionError: Lists differ: ['程序/docs/process/用户沟通与要求标准.md'] != []
新增文件必须在 distribution_manifest.md 里声明保留或排除
```

原因：R3989 新增这份文档时没有在分发清单里声明。`docs/process/` 下的文件在清单里是逐个列的，不像 `docs/records/**`、`docs/specs/**` 按目录覆盖；这条检查不在合入检查（默认冒烟、静态门禁、架构门禁）里，所以合入时没拦住，到后台全量才红。补声明后 `tests.test_distribution_selfcheck` 3 条全过。

防止再犯：`codex/doc-format` 车道新增的 `docs/process/阶段文档写法.md` 有同样的问题，合入前要补声明；以后新增文档的车道，合入前加跑 `tests.test_distribution_selfcheck`。这两条已写进会话接续记录。

## 4. 没做的和已知限制

1. 同一次全量的另一个红文件 `test_round_claim`（11 条）没有修：`scripts/dev.py claim` 的返回码正确，但标准输出和标准错误都是空的。本轮在车道里单独跑了其中两条用例（`test_claim_new_branch_rejects_bad_names_before_any_state_write`、`test_dev_claim_forwards_valid_new_branch_and_preserves_claim_registration`），都通过；全量日志标了 `[SUSPECT_CONCURRENCY]`，当时有 11 条车道同时在跑。按高负载下的偶发红记账，根因没查明。
2. 会话接续记录里「等合入的分支」写的是 08:20 的状态，之后逐条合入；合没合以 `git log master` 为准。会话收尾时再改一次这一节。
3. 2026-11-20 之前的会话没有回补，回补另出任务卡。
4. 《用户沟通与要求标准》仍是草稿，等用户确认。
