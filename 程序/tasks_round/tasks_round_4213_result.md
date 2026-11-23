# R4213 结果：补登记 合入前预览说明（DOC-PREVIEW-GUIDE 合入前的登记补笔）
<!-- round-evidence: {"commit_base": "25b5ac17", "credential_hits": 0, "evidence_sha256": "5aed7890412eba17", "exit": 0, "failed": 0, "passed": 0, "round": 4213, "tests": "docs-only"} -->

## 开头三问

- （一）本轮属于哪种类型：纯文档轮的登记补笔（不涉及 REQ/DES）。只改 `docs/records/工程文档登记表.md` 一行并新建本结果文件；不改任何 `.py`、不改 runbook、AGENTS.md。车道 `codex/doc-preview-guide`，由验收窗口（总控）在 R4206 的提交之上补做。
- （二）测试跑了吗、三个基线：跑了 `run_selftests.py -k doc_registry_migration`（7 条，全过，退出码 0）；出口 CI 其余两项与架构门禁由合并轮 `dev.py merge` 在本车道重跑。
- （三）欠账少了吗：少了。R4206 结果文件「如实说明（一）」登记的「新文档未进工程文档登记表」这条欠账本轮还掉。

## 为什么由验收窗口补

- R4206 合并轮 23:50 在本车道跑出口 CI，架构门禁红在 `test_doc_registry_migration.test_all_current_documents_are_registered`（`存在但未登记：docs/guides/合入前预览说明.md`），未占主干、未领号。
- 该卡的允许修改文件不含登记表，执行者已在结果文件里如实上报并请总控裁定。用户已授权纯文档变更省去逐步确认；这是登记表一行、由同一条机器门禁复核，所以由总控直接补登，不另开卡。

## 改了哪些文件

- `程序/docs/records/工程文档登记表.md`：在 `docs/guides/编剧功能说明.md` 行后新增一行 `docs/guides/合入前预览说明.md | 全局 | 全局 | 派生 | R4206 | 用户`。性质写「派生」：全文内容出自 runbook §12，唯一依据仍是 runbook。
- `程序/tasks_round/tasks_round_4213_result.md`：本文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k doc_registry_migration` | 7 条全过，退出码 0 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 领到轮次 4213 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4213: 补登记 合入前预览说明" docs/records/工程文档登记表.md tasks_round/tasks_round_4213_result.md` | 见队列证据 |

## 未验证

- 没有在合并轮之外另跑出口 CI；合并轮通过与否记在队列项 DOC-PREVIEW-GUIDE 的证据里。
- `文档导航.md` 没有加这份指南的链接（不在本笔范围，纯链接，不影响门禁）。
