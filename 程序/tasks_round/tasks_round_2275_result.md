# R2275 「工作流任务」手拼改用入口：projects／download_inbox／shot_numbering（J23 结构治理轮·第 7 批）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 09 的 J23。

## 基线
分支 `codex/wip-R2275`，自 `codex/wip-R2274`。

## 轮次类型／三套基线／债务
结构治理轮；路径逐字等价；无新增债务。

## 改动
- `projects.py`（3 处名称比较）、`download_inbox.py`、`shot_numbering.py`：字符串字面量改 `stage_layout.WORKFLOW_DIR`／`workflow_dir`。
- `tests/architecture/test_workflow_dir_ratchet.py`：三模块降到 0 并移除登记（断言未动）。

## 新增测试
无。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k projects download_inbox shot_numbering workflow_dir` 23 条全过；`smoke_test.py --architecture` 仅已知两项环境红。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
J23 第 8 批：workflow_engines；storyboard_recycle_service 随 J-回收轮清零。
