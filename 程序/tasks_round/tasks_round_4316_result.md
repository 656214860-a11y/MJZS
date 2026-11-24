# R4316 · WORKTREE-SUBMODULES：工作树子模块初始化脚本与测试
<!-- round-evidence: {"commit_base": "b52a39ef1", "credential_hits": 0, "evidence_sha256": "bf346d5a5bc29a87", "exit": 0, "failed": 0, "passed": 8, "round": 4316, "tests": "run_selftests.py -k seed_worktree_submodules"} -->

## 开头三问

- （一）本轮类型：功能轮（开发脚本），车道 `codex/worktree-submodules`，基准 `master` `b52a39ef1`。
- （二）测试跑了吗、三个基线：定向 `run_selftests.py -k seed_worktree_submodules` 8/8 通过（0 红）；默认冒烟与完整架构门禁由合入出口 CI 覆盖；全量回归未跑（以 `full-safe-receipts.json` 为准）。
- （三）欠账少了吗：未新增欠账。

## 改动文件

- `程序/scripts/seed_worktree_submodules.py`：新增工作树子模块种子脚本。
- `程序/tests/test_seed_worktree_submodules.py`：新增 8 条单元测试。
- `程序/tasks_round/tasks_round_4316_result.md`：本文件。

## 验证记录

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `run_selftests.py -k seed_worktree_submodules` | 0 | 8 条全绿，0 红 |
