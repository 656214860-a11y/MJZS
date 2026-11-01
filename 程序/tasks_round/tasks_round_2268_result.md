# R2268 「工作流任务」手拼改用入口：pet_agent／pet_llm／pet_performance_service（J23 结构治理轮·第 2 批）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 09 的 J23。

## 基线
分支 `codex/wip-R2268`，自 `codex/wip-R2264`。

## 轮次类型／三套基线／债务
结构治理轮；路径逐字等价；无新增债务。

## 改动
- `pet_agent.py`、`pet_llm.py`：路径元组首项改 `stage_layout.WORKFLOW_DIR`（import 并进既有行，行数不增）。
- `pet_performance_service.py`：元组首项同上，基线路径改 `stage_layout.workflow_dir(...)`。
- `tests/architecture/test_workflow_dir_ratchet.py`：三模块降到 0 并移除登记（断言未动）。

## 新增测试
无。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k pet_agent pet_llm pet_perf pet_state workflow_dir` 169 条全过；`smoke_test.py --architecture` 仅已知两项环境红。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
J23 第 3 批：pet_report、pet_state、pet_test_service。
