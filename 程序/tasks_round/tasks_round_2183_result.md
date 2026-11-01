# R2183 结果：合入 codex/wip-R2181（R2181：剧本准备页紧凑布局测试同步 R2131 的提示锚点，更正 R2165、R2169 的全量记录）到 master（合并轮）

## 三问
- 轮次类型：合并轮（§3）。
- 测试和三个基线：在主检出 master 合并后的树上运行（经 gui_hidden）。
  - `run_selftests.py -k test_desktop_compact_layout`：5 条全过（15.6 秒）。
  - 默认冒烟：通过 8 项，失败 0 项。
  - `smoke_test.py --architecture`：411 项，只有 `test_full_safe_all_is_required_after_eight_source_rounds` 失败（本轮欠一次完整安全全量，提交后补跑），其余全过。
  - 全量 `--all --safe`：本轮按 §5 必须跑（master 提交点，上次全量通过停在 R2124，之后源码轮已超过 8 个）。全量要对本轮提交后的 HEAD 跑，所以放在提交之后：先看 post-commit 钩子有没有启动后台全量，没有就在主检出手动执行 `scripts/auto_full_safe.py --spawn`。结果在本文件提交之后才出，这里不写通过与否，以 `logs/auto_full_safe.log` 和全量凭据为准。
  - 真机未手动核对：本轮没有改产品代码。
- 轮次号：领号放在提交前一刻，在干净的 worktree 里领到 R2183，主检出没有被切走分支。
- `project_status.md` 欠账：没有减少，也没有新增；本轮把当前轮次更新为 2184。

## 合并内容
- `git merge --no-ff codex/wip-R2181`，自动合并，无冲突。4 个文件：`tests/test_desktop_compact_layout.py`、`tasks_round/tasks_round_2165_result.md`、`tasks_round/tasks_round_2169_result.md`、`tasks_round/tasks_round_2181_result.md`。
- 改动说明见 `tasks_round/tasks_round_2181_result.md`。测试只把提示层锚点的期望值从 `'w'` 改为 `'nw'`，同步 R2131 有意变更的 UI 契约（§2.4）。R2181 测试契约有意变更，其余断言未动，没有删除、放宽或跳过断言。
- R2181 同时更正了 R2165、R2169 两份结果文件里「由提交后钩子后台补跑全量」的记录：那两次提交后钩子都没有启动后台全量。
- 主检出未提交的 `.claude/settings.local.json` 不属于本轮，未暂存。
- 本轮没有改产品代码，不用重启应用。
