# R2512 结果：结构治理轮——覆盖率基线模块数收尾（R2509 拆分连锁刷新）

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮（§3.3·执行）——R2509 拆出 `desktop_idea_attachments.py` 后，master 上又合入 R2506（新增 L0 模块），覆盖率基线 `modules_total` 从 364 漂移到 365 但基线文件仍记 364，导致 `test_baseline_is_self_consistent` 红。本轮重跑 `coverage_report.py` 刷新基线、同步 runbook §11 的模块数 364→365。

2. **测试跑了吗、三个基线过了吗？**
   - **架构门禁 `smoke_test.py --architecture`**：**420/420 全绿（exit 0）**（刷新前 420 条 1 红 `test_baseline_is_self_consistent`：364 != 365）。
   - 定向／默认冒烟：本轮只改 runbook + 覆盖率基线两个文档/数据文件，无源码，不另跑定向；架构门禁已覆盖一致性。

3. **`project_status.md` 的欠账少了吗？**
   架构门禁欠账归零（上一轮 R2510 合并后 master 上是 1 红，本轮刷新后 0 红）。

## 改动清单

- `程序/维护记录/覆盖率基线.json`：`coverage_report.py` 重跑刷新，`modules_total` 364→365（覆盖 59 个不变，新增模块为 R2506 的 L0 模块）。
- `程序/runbook.md`：§11 模块数 364→365、其余 305→306。

## 提交

- 轮次类型：结构治理轮；经 `dev.py claim` 领取 R2512。
- 本轮已提交：分支 `codex/wip-R2511`，提交标题 `R2511: …`（不写死 hash，查 `git log --oneline -1`）。仅本工作树分支，**未合入 master、未 push**。
