# R2274 「工作流任务」手拼改用入口：stage_download_inbox_service／storage_maintenance／white_model_service（J23 结构治理轮·第 6 批）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 09 的 J23。

## 基线
分支 `codex/wip-R2274`，自 `codex/wip-R2273`。

## 轮次类型／三套基线／债务
结构治理轮；路径逐字等价；无新增债务。

## 改动
- `stage_download_inbox_service.py`、`storage_maintenance.py`（回收站路径）、`white_model_service.py`：手拼改入口。
- `tests/architecture/test_workflow_dir_ratchet.py`：三模块降到 0 并移除登记（断言未动）。

## 新增测试
无。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k storage recycle white_model download_inbox workflow_dir` 140 条 条全过；`smoke_test.py --architecture` 仅已知两项环境红。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
J23 第 7 批（含 projects、download_inbox 等名称比较类）：projects、download_inbox、shot_numbering。
