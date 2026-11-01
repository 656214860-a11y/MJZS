# R2185 结果：合入 codex/wip-R2182（R2182：钩子导出的 GIT_DIR 让欠账算成 0，master 提交后后台全量从不启动）到 master（合并轮）

## 三问
- 轮次类型：合并轮（§3）。
- 测试和三个基线：在主检出 master 合并后的树上运行（经 gui_hidden）。
  - `run_selftests.py -k auto_full_safe git_hooks`：41 条，0 个文件有红（3.6 秒）。
  - 默认冒烟：通过 8 项，失败 0 项。
  - `smoke_test.py --architecture`：411 项全过，含 `test_round_number_continuous` 和 `test_full_safe_all_is_required_after_eight_source_rounds`。
  - 全量 `--all --safe` 本轮不欠，未运行。R2183 提交后，原会话手动执行 `--spawn` 起了一次全量（HEAD 6ce35959）：13:30:14 开始，13:42:02 结束，709 秒，退出码 0，凭据 `last_full_safe_all_round` 为 2183。2183 之后只有本轮的合并提交，源码轮次算 0，不到后台触发线 6：`git log --name-only` 不列合并提交的文件，R2182 的轮次号又小于 2183。
  - 真机未手动核对：本轮没有改产品代码，不用重启应用。
- 轮次号：领号放在提交前一刻，在干净的 worktree（分支 `codex/wip-R2182`）里领到 R2185（R2184 已被分支 `codex/wip-R2184` 的结构治理轮领走），主检出没有被切走分支。
- `project_status.md` 欠账：没有减少，也没有新增；本轮把当前轮次更新为 2185。

## 合并内容
- `git merge --no-ff --no-commit codex/wip-R2182`，自动合并，无冲突。3 个文件：`scripts/auto_full_safe.py`、`tests/test_auto_full_safe.py`、`tasks_round/tasks_round_2182_result.md`。
- 改动说明、先红后绿的输出和模拟验证见 `tasks_round/tasks_round_2182_result.md`；已有测试断言未动。
- 钩子文件没改。钩子调用的是主检出的 `程序/scripts/auto_full_safe.py`，合入即生效，不用重装钩子。
- 分支没有改 `project_status.md`，没有共享状态文件要合并。§2.6 第 41 条的两条核对命令在提交前对暂存区执行，内容与提交后的 HEAD 相同：第一条输出为空；第二条得到 100 个轮次号，与合并前 master（6ce35959）逐条相同。
- 主检出未提交的 `.claude/settings.local.json` 不属于本轮，未暂存。

## 完成标准的现场核对：本轮核对不了
- R2182 的完成标准是「从 Claude 会话的 Bash 工具用 `dev.py commit` 提交 master 后，`auto-full-safe.lock` 出现、`logs/auto_full_safe.log` 开始写」，前提是提交时欠账已到触发线。R2183 之后补跑的全量是绿，欠账清零，本轮提交后钩子按设计不起全量，锁和日志都不该出现。在这次提交上，修复前后的代码判断结果相同，现场分不出差别。
- 替代证据：合并后在主检出（真实仓库和历史）上，按钩子的方式从仓库根运行，数 R2124 之后、到 R2185 为止改过源码的轮次：

| 环境 | 直接调 `run_selftests.source_rounds_since` | 经修复后的 `auto_full_safe.main()` 入口 |
| --- | --- | --- |
| 无 `GIT_*` | 16 | 16 |
| 钩子导出的 `GIT_DIR`、`GIT_INDEX_FILE` | 0 | 16 |

  经入口调用返回后，`GIT_DIR` 原样还原。
- 留给下一次：2183 之后累计 6 个源码轮的那次 master 提交，或改到启动入口、`storage_maintenance.py`、层级登记表的轮次，提交后 `auto-full-waiter.lock` 应立刻出现。欠账没满 8 轮时，等待者先等 15 分钟安静期，然后 `auto-full-safe.lock` 出现，`logs/auto_full_safe.log` 开始写。

## 范围外（只记录，未改）
- 欠账按提交说明里的轮次号计。合入时轮次号已小于 `last_full` 的分支轮（如本次的 R2182），它的源码改动不会计入任何一次欠账；合并提交本身也不计。R2182 只改开发脚本和它的测试，定向自检已覆盖。
