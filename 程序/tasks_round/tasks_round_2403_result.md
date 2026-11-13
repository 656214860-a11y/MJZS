# R2403 结构治理轮·执行：项目目录整理 + 文档导航

## 本轮三个问题

- **本轮类型**：§3.3 结构治理轮·执行（只清理/移动文档，不改源码；未动分层、契约或权威源，故不更新 architecture.md）。
- **测试**：默认冒烟 `smoke_test.py` 8/8 通过；`test_distribution_selfcheck` + `test_root_layout` 4/4 通过（含 `test_manifest_covers_every_file`、`test_tracked_root_entries_are_registered`）。未跑全量（本轮无源码改动，§5 不触发全量，不冒领全量凭据）。
- **欠账**：`project_status.md` 无欠账变化（本轮不新增/不清欠账，仅清理历史证据与新增文档导航）。

## 改动清单（10 项）

**删除（8 个过期交接单，历史仍可经 git 追溯）**：

- `HANDOFF_20261023_0400.md`、`HANDOFF_20261023_goal.md`、`HANDOFF_20261023_会员账号后续.md`
- `HANDOFF_AUTO_20261022_2147.md`、`HANDOFF_AUTO_20261022_2245.md`、`HANDOFF_AUTO_20261023_0104.md`、`HANDOFF_AUTO_20261023_0230.md`、`HANDOFF_AUTO_20261023_0325.md`

删除理由：均为 2026-10-22/23 的一次性会话交接快照，内容已被 `tasks_round/` 结果文件与 `project_status.md` 完全吸收；符合「`.agent-handoff` 停更、历史看 git、不再新增交接单」的既有约定。`HANDOFF_20261022_1830.md` 因工作树有未提交改动（非本轮产生），保留未删。

**修改（1 项）**：

- `distribution_manifest.md`：移除已删 HANDOFF 的保留声明，改为只保留现存的 `HANDOFF_20261022_1830.md`，并登记新增的 `程序/文档导航.md`（否则 `test_manifest_covers_every_file` 红）。

**新增（1 项）**：

- `文档导航.md`：简洁中文文档导航，覆盖入口、用户说明、设计规范、运行数据、阶段文档、说明库、历史台账七个层次，每项一句话用途 + 阅读顺序。

## 保留未动（记录说明）

- `程序/crud_audit_20260926.md`：R1455 已裁定「历史审计，保留原件」，不移动。
- 两份根 `.ico`：字节相同但职责不同（正式图标 vs 桌面快捷方式指向），R1467/R1468 已裁定不能当重复删。
- `程序/tasks_round/`、`维护记录/`、`说明/`、`docs/`：可复现轮次史与审计台账，不删。
- `程序/.selftmp/` 及子目录：ACL 为 `CodexSandboxUsers` 所有，当前用户非管理员无删除权限，`takeown`/`icacls` 均失败，保留并记录为真实 ACL 阻塞。
- `.claude/worktrees/`（346MB）、`.wt/`（43MB）、`运行环境/*_backup`：worktree 备份，删除须经 `worktree_ledger.py --plan` 逐项确认，不在本轮范围。

## 提交状态

- 提交信息：`R2403: 项目目录整理（删除8个过期交接单）＋新增文档导航`
- commit hash：见提交结果（本轮未提交时留空，提交后回填）。
