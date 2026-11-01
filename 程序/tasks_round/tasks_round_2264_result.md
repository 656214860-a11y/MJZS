# R2264 「工作流任务」手拼改用入口：agent_dispatch／codex_tasks／workflow_settings（J23 结构治理轮·第 1 批）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 09 的 J23：「23 个模块每轮 ≤3 个改用入口，棘轮登记逐轮下调直至清空」。

## 基线
分支 `codex/wip-R2264`，自 `codex/wip-R2262`。

## 轮次类型／三套基线／债务
结构治理轮；路径结果逐字等价；无新增债务。

## 改动
- `agent_dispatch.py`、`codex_tasks.py`、`workflow_settings.py`：手拼 `'工作流任务'` 改为 `stage_layout.workflow_dir(...)`（`workflow_settings` 的 import 并进已有一行，行数不增）。
- `tests/architecture/test_workflow_dir_ratchet.py`：三模块降到 0，从 REGISTERED 移除（其余不动，断言未动）。

## 新增测试
无（既有 `test_workflow_dir_authority`、棘轮测试覆盖）。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k agent_dispatch codex_tasks workflow_settings workflow_dir size_ratchet` 全过；`smoke_test.py --architecture` 仅已知环境红。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
J23 第 2 批：pet_agent、pet_llm、pet_performance_service。
