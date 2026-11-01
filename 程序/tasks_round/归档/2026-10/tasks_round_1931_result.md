# R1931 结果：提交流程提速（功能轮）

- 起因：会话记录统计显示"提交"步骤常卡住。实测 git 本身 <1 秒；真因有二：
  1. pre-commit 在后台全量验收持锁（`full-safe-selftest.lock`）时拒绝提交，会话靠 `sleep 20` 重试，最长 2474 秒；锁持有进程已死时钩子仍拒绝。
  2. `round_claim.py next` 在工作树有未提交改动时拒绝领号，而 WIP 分支名需要先知道轮次号。
- 改动：
  - 新增 `scripts/commit_round.py`，接入 `dev.py commit`：暂存、按暂存清单生成白名单、进程内等验收锁（失效锁回收、默认等 30 分钟）、提交。钩子规则未动。
  - `round_claim.py next`：脏树不再拒绝，领号后 `git switch -c codex/wip-R<号>` 带走改动；游离 HEAD 仍拒绝且不分配。
  - `CLAUDE.md` 增加提交入口说明。
- 测试：`test_commit_round`（新）、`test_round_claim`、`test_git_hooks`、`test_claim_queue_gateway`、`test_dev_entry` 在隐藏桌面通过；未跑 smoke／全量。
- 测试契约变更：`test_dirty_next_cli_refuses_without_allocating_and_suggests_wip_branch` 改为 `test_dirty_next_cli_claims_then_parks_changes_on_wip_branch`（拒绝契约有意改为自动 WIP 分支）；其余断言未动。
- 欠账：未减少。
