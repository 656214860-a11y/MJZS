# R2276 「工作流任务」手拼改用入口：workflow_engines（J23 结构治理轮·第 8 批）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 09 的 J23。

## 基线
分支 `codex/wip-R2276`，自 `codex/wip-R2275`。

## 轮次类型／三套基线／债务
结构治理轮；路径逐字等价；无新增债务。

## 改动
- `workflow_engines.py`（4 处）：手拼改 `stage_layout.workflow_dir(...)`。
- `tests/architecture/test_workflow_dir_ratchet.py`：三模块降到 0 并移除登记（断言未动）。

## 新增测试
无。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k workflow_engine claude codex workflow_dir` 58 条全过；`smoke_test.py --architecture` 仅已知两项环境红。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
J-回收：storyboard_recycle_service 改走 recycle_paths（同时清空登记表）。
