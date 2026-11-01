# R2262 路径权威加「工作流任务」入口（J22 契约轮）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 09 的 J22：「路径权威加『工作流任务』入口（落 L0 时按契约轮）」。

## 基线
分支 `codex/wip-R2262`，自 `codex/wip-R2260`。

## 轮次类型／三套基线／债务
契约轮（L0 `stage_layout` 新增只读入口，不改既有函数）；无新增债务。

## 改动
- `stage_layout.py`：新增 `WORKFLOW_DIR = '工作流任务'` 与 `workflow_dir(project, *parts)`。
- `tests/architecture/test_workflow_dir_ratchet.py`：路径权威 `stage_layout.py` 自身产出该目录名，不计入棘轮（其余登记与下降规则不变，断言未动）。

## 新增测试
`tests/test_workflow_dir_authority.py`：`workflow_dir` 拼接与常量。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k workflow_dir stage_layout stage_path` 全过；`smoke_test.py --architecture` 412 条，仅两项已知环境红。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
J23 起：23 个模块每轮 ≤3 个改用入口，登记逐轮下调。
