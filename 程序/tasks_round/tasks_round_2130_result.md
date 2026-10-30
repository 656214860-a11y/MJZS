# R2130 结果：合入 codex/wip-R2129（R2129：一份下载只收回到最近一次派发登记的位置）到 master（合并轮）

## 内容
- R2129（9132c3a4）：`download_inbox.match_registered` 按下载件分组，只写到派发时间最新的登记位置，其余对上同一份下载的登记一并销账（REQ-S01-74／DES-S01-74）；详见 tasks_round_2129_result.md。

## 合并前检查
- 主检出在 master，无 MERGE_HEAD，暂存区为空，只有用户自己的 `.claude/settings.local.json` 未提交改动（未暂存、未提交）。
- `--no-ff` 合并，无冲突。

## 验证（本轮运行，合并后的主检出）
- `run_selftests -k download_inbox idea_download flow_agent_launch desktop_send_ledger media_publish stage_execution req_s01_anchors requirement_traceability`：全部通过。
- `smoke_test.py --architecture`：合并后、更新状态页前唯一红为 `test_round_baselines.test_round_number_continuous`（状态页当前轮次 2128 ≠ 最新结果号 2129＋1），由本次状态页更新解决；其余全部通过。
- `--all --safe`：由本次提交的 post-commit 钩子在后台触发。
