# R2611 结果：车道范围门禁——开工查重＋提交时新增文件撞名拦截
<!-- round-evidence: {"commit_base": "ddda856c", "credential_hits": 0, "evidence_sha256": "7200cca12f3c861b", "exit": 0, "failed": 0, "passed": 24, "round": 2611, "tests": "run_selftests.py -k branch_scope commit_round worktree_ledger"} -->

## 类型与三问

- 类型：功能轮（开发期门禁工具，不改产品运行时行为）。
- 测试：`tests/test_branch_scope.py` 11 条、`test_commit_round`＋`test_worktree_ledger` 13 条、`run_selftests.py -k commit_round branch_scope worktree_ledger dev.py gate_selfaudit` 30 条全绿；默认冒烟 8/8；`coverage_baseline`＋`complexity_ratchet` 绿。
- project_status 欠账：无新增。

## 背景与方案

- 起因：R2542（devin-gates-b4）与 R2538（SWE-2 闸门栈）对「工程闸门批次4」各自独立实现，合入时 6 处 add/add/content 冲突。根因是轮次号与队列锁只管编号不管范围，两条车道从共享计划文档各自取活互不可见。
- 方案（两层）：
  1. **开工前扫描** `dev.py scope <路径>...`：新模块 `维护记录/基准脚本/branch_scope.py` 枚举 `git worktree list` 中带分支引用的活跃工作树，逐分支算 `git diff master...branch` 改动集，与计划路径求交输出重叠；`--added` 只看新增文件口径，`--json` 机器可读。
  2. **提交门禁** `commit_round.check_scope_overlap`：暂存区 `diff --cached --diff-filter=A` 新增文件与其他活跃分支新增文件同名即拒绝（exit 5）；合并提交（MERGE_HEAD）与 master/main 不触发——被合入的源分支本就含同名新文件，属正常合并。读取失败的分支只警告不阻断。
- 「活跃分支」口径：带分支引用的工作树；无工作树的未合并分支视为停放/遗留不阻断，风险由合并轮 CI 兜底。

## 改动文件

- `程序/维护记录/基准脚本/branch_scope.py`（新增）
- `程序/scripts/commit_round.py`（import＋check_scope_overlap＋接入主流程，位于 test_move/evidence 之间先失败）
- `程序/scripts/dev.py`（`scope` 子命令＋docstring）
- `程序/tests/test_branch_scope.py`（新增 11 条，真实临时 Git 仓库）
- `程序/runbook.md`（§13 新增「车道范围门禁（R2611 起）」段）

## 验证

- 新测试覆盖：撞名拦截、无暂存新增不触发、无关新文件放行、已合入车道不阻断、前缀/边界匹配、added_only 口径、detached 工作树不算车道、`check_scope_overlap` 返回码、CLI JSON。
- 真实仓库冒烟：`dev.py scope` 枚举 25 个活跃分支正常；本轮新增文件与其他分支零撞名。

## 提交

- 待回填 hash。
