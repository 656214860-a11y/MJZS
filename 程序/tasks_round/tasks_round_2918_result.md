# R2918 结果：T9 仓库卫生收口——.err 归档出库＋CHANGELOG 版本策略
<!-- round-evidence: {"commit_base": "48bf43c7", "credential_hits": 0, "evidence_sha256": "0754807c0ea79f54", "exit": 0, "failed": 0, "passed": 0, "round": 2918, "tests": "docs-only"} -->

## 三问

1. **轮次类型**：结构治理轮（仓库卫生；只移文件、改 `.gitignore` 与 `CHANGELOG.md`，无产品逻辑、无 `.py` 改动）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；定向 26 条（`test_status_page_size` 2＋`test_round_baselines` 5＋`test_agents_md` 15＋`test_archive_results` 4）全绿，证据 `evidence/R2918.json`；未跑全量（无源码逻辑改动，docs-only 口径）。
3. **欠账少了吗**：是。T9 剩余的 `.err` 调试输出归档与 `*.err` 忽略规则本轮收口；CHANGELOG 语义化版本策略补齐（release_snapshot 接入此前已存在，经 `_version()`→`app_metadata.VERSION` 自动消费）。tasks_round 归档经复核确认已于 R2721 完成（见下「T9 复核结论」）。

## 本轮交付

| 项 | 内容 |
|---|---|
| `.err` 归档 | 21 个被跟踪的 stderr 调试输出（8 个 `r702_*.err`＋13 个 `r713–r723_*.log.err`，均 2026-10-02 入库的历史自检残留）移出版本库，落本机 `程序/维护记录/归档/2026-10/`。该目录在 `.gitignore` 中本就是「本机证据、不入库」区（先例：`运行日志归档_*.zip` 同样不跟踪）；内容仍可从 git 历史与 tag `archive-err-pre-R2918`（已推 `backup`）恢复。 |
| `.gitignore` | 新增 `*.err`，今后 stderr 调试输出不再入库。 |
| `CHANGELOG.md` | 新增「版本策略」节：`VERSION` 唯一权威在 `contract/app_metadata.py`（当前 `V0.7`），`V<主>.<次>` 方案，里程碑合入时归档「未发布」条目；R<N> 轮次号不进版本号。 |

## 归档前置与引用核查

- 先打 tag `archive-err-pre-R2918`（指向 `48bf43c7`）并推 `backup`：pre-receive 全树扫描通过，post-receive 正确判定 0 个 CI ref。
- 移动前 grep 全库：21 个文件仅被 `tasks_round/归档/2026-10/` 内的历史结果文件提及（R702/R713 等轮次记录），无存活代码、测试、门禁或文档引用，无需修路径。
- `distribution_manifest.md` 第 41 行已将 `维护记录/**` 列为「可再生成的诊断输出」，无需更新。

## T9 复核结论（任务书逐项）

| 任务书条目 | 结论 |
|---|---|
| tasks_round 归档（约 1950 文件） | **已完成**（R2721 轮）：`tasks_round/归档/` 现有 1683 个文件（2026-10、2026-11_历史文档等）；`scripts/archive_results.py` 干跑预览「平铺 423 份、将归档 0 份」——近期窗口内无可归档项，`N == M + 1` 连续性由 `test_round_baselines`/`test_status_page_size` 守卫。tag `archive-pre-R2721` 已在 `backup`。 |
| `维护记录/*.err`、`*.log.err` 归档＋`.gitignore` | **本轮完成**（见上）。 |
| `docs/adr/` 重大决策 | **已存在**：`docs/adr/0001-layered-architecture.md`。 |
| `CHANGELOG.md`＋语义化版本＋`release_snapshot.py` 接入 | **本轮补齐策略文档**；机械接入此前已存在（`release_snapshot.py` → `distribution_build._version()` → `app_metadata.VERSION`）。 |
| `GLOSSARY.md` 术语表 | **已存在**：覆盖三虎、棘轮、轮次、权威源、分层、冒烟/架构门禁/全量、验收锁、SKILL、总控 SKILL、分发副本。 |
| 瘦身 `project_status.md`／`architecture.md`／`AGENTS.md` | **达标**：`project_status.md` 19.5 KB（任务书时约 90 KB，历史已迁 `维护记录/状态历史归档.md`）；`AGENTS.md` 15.9 KB ≤ 16 KB 上限；`architecture.md` 64.6 KB 全文为现行权威内容（目录树、SKILL 清单、分层、门禁清单），无历史段可迁——其体积主要来自「当前架构门禁清单」，按契约必须与 `tests/architecture/` 实际文件集合完全相等，不可压缩。 |

## 轮次号说明

R2917 在主工作区误调用 `round_claim.py next` 时被领取并绑定 master（未产生任何改动与结果文件），按既有跳号惯例放弃；本轮实际使用 R2918。`round_claim.py validate` 0 errors。

## 验证记录

- `run_selftests.py -k status_page_size round_baselines agents_md archive_results`：26 条全绿（工作树内补入本机 `基准历史.json` 后；该文件 gitignore、本机诊断用）。
- `smoke_test.py`：8/8 通过。
- 未跑：`--architecture` 全量（定向已覆盖文档一致性三件套）、`--all --safe` 全量（无源码逻辑改动）。
