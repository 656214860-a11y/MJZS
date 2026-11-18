# R3497 结构治理轮结果（作废工作树清理）
<!-- round-evidence: {"commit_base": "eed48da2", "credential_hits": 0, "evidence_sha256": "60063fdf5b75027d", "exit": 0, "failed": 0, "passed": 0, "round": 3497, "tests": "docs-only"} -->

- 轮次类型：结构治理轮（仓库卫生／工作树治理，纯环境维护＋台账文档；未改 .py）。
- 三问：测试——已跑默认冒烟 9/9 通过（未改 .py，未跑 selftest/全量）；三个基线——冒烟实测 9/9、架构门禁与全量凭据本轮未触发；欠账——未新增，历史欠账不变。
- 范围：用户授权「清理作废工作树」，逐档确认后只执行第 1+2 批机械安全项，并顺带删除已合并且无工作树的本地分支；KEEP/BLOCK 树一律未动。

## 执行明细

- 盘点：`维护记录/基准脚本/worktree_ledger.py` 只读扫描，登记工作树 115（KEEP 99／RECYCLE 11／BLOCK 5）、未登记残留 10、分支 205。
- `git worktree remove --force` ×13：11 个 ahead=0 空转树（分支已合入 master）＋2 个 detached 且 HEAD 经 `merge-base --is-ancestor` 验证已含于 master（skill-budget-verify-c351ca11、tmp-ledger-check2）。`--force` 仅绕过 gitlinks 子模块占位检查；子模块 checkout 抽查干净、HEAD 与 gitlink 一致且带 GitHub remote，可复现。
- 残留壳 ×3 手工清理：granite-difference／devin-l1-infra／dsh-864fd932-4054 因 `运行环境` junction/symlink 触发 Invalid argument；注册项已移除，余壳仅含该链接，断链后 rmdir，链接目标完好。
- 空目录 ×2：`.codex/worktrees/r856`、`.agents/worktrees/devin-fixgate`。`git worktree prune --dry-run` 无目标。
- `git branch -d` ×51：merged 且无工作树（11 个来自本次被拆树，40 个历史已合并）。删后 merged 无树分支余 26，全部仍挂工作树。

## 未动与遗留

- 99 个 KEEP 树（独有提交/脏/锁定/活跃）、`.wt/ci` 与 `devin-debt-R2548/.wt/ci` 锁定 CI 树、当前会话 brass-flywheel。
- `dsh-fd0dbe5a-3281` 坏树（status 被失效嵌套仓库阻断，需 --force 且未提交态不可查）、8 个 `.codex/worktrees` 未登记残留目录——均列入台账待后续裁定。
- 明细与证据见 `维护记录/工作树精简台账.md` R3497 节。

## 提交

- 分支 `brass-flywheel`，提交信息 `R3497: ...`；证据文件 `tasks_round/evidence/R3497.json` 由 commit_round 自动生成并盖章。
- 本分支尚需合入 master（合并轮另行处理）。
