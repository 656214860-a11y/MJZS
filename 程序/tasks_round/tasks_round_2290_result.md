# R2290 结果：流程三项（结果文件按月归档、状态页行数上限、合并轮一条命令）（功能轮）

## 三问
- 做了什么：①`dev.py archive` 把旧月份结果文件 `git mv` 到 `tasks_round/归档/<年-月>/`（预览默认，`--apply` 执行；保留本月，最新一份不动）；已归档 R151–R2151 共 1652 份，平铺目录只剩 114 份。领号（`round_claim`）、`run_selftests.latest_completed_round`、`test_round_baselines`、`test_skip_hygiene` 改递归匹配，最大轮次号仍为 2286。②新增架构门禁 `test_status_page_size.py`：`project_status.md` ≤500 行（当前 469）。③新增 `dev.py merge <分支> -s 说明`：在 master 检出里先 `--no-commit` 试合并（冲突即中止、不领号），成功后领号、改状态页抬头（只保留前一轮首句）、写结果文件，交 `commit_round` 提交。
- 为什么：结果文件已 1766 份平铺；状态页无上限；合并轮要手工做五步。
- 没做：未跑全量；合并命令只测了纯函数部分，真实合并在本轮合入时首次使用；未推送。

## 红绿
- 红：`test_archive_results.test_latest_result_round_sees_archived_files` 改前 `AssertionError: 5 != 9`（旧的非递归匹配看不到归档文件）。
- 绿：`run_selftests.py -k agents_md status_page merge_round archive_results round_baselines skip_hygiene round_claim selftests` 全过。断言未动。
- `smoke_test.py --architecture`：413 例仅余 worktree 缺 gitignored `基准历史.json` 一项（临时拷入后同组测试全过，未提交该文件）；`architecture.md` 门禁清单已登记新测试。

## 基线
- 凭据扫描：本轮未触碰密钥与数据边界目录。
- 全量欠账：上次全量 R2256 绿；本轮不计入源码改动轮之外的新增欠账以外。
