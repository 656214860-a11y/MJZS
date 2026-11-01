# R2272 「工作流任务」手拼改用入口：previs_automation／previs_batch_service／previs_routing（J23 结构治理轮·第 4 批）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 09 的 J23。

## 基线
分支 `codex/wip-R2272`，自 `codex/wip-R2269`。

## 轮次类型／三套基线／债务
结构治理轮；路径逐字等价；无新增债务。

## 改动
- `previs_automation.py`、`previs_batch_service.py`、`previs_routing.py`：手拼改 `stage_layout.workflow_dir(...)`（routing 共 2 处）。
- `tests/architecture/test_workflow_dir_ratchet.py`：三模块降到 0 并移除登记（断言未动）。

## 新增测试
无。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k previs workflow_dir` 133 条全过；`smoke_test.py --architecture` 仅已知两项环境红。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
J23 第 5 批：qwen_adapter、skill_budget、skill_tools。
