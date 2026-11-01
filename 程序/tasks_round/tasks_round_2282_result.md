# R2282 Cloud 滚动小字状态收进 CloudHintState（J-Cloud 结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 07 的 J-Cloud：「挑一簇多写者属性收进只由一个 Mixin 写的状态对象，棘轮下调」。

## 基线
分支 `codex/wip-R2282`，自 `codex/wip-R2281`。

## 轮次类型／三套基线／债务
结构治理轮；行为等价；无新增债务。

## 改动
- `pet_cloud_hint.py`：新增 `CloudHintState`（`job/on/x/user_focus`，默认值与原四个属性一致）；Mixin 内读写改 `self.hint_state.<字段>`。
- `pet_cloud.py`：`__init__` 的 `_hint_job/_hint_on/_hint_x/_hint_user_focus` 四行换成一行 `self.hint_state = CloudHintState()`（两处读取同改）；Tk 标签 `hint` 仍是控件属性，不收进状态对象。
- `tests/test_leak_teardown.py`、`tests/test_pet_ui.py`：模拟宿主与断言的读取路径随属性名同步（`cloud._hint_job`→`cloud.hint_state.job`、`cloud._hint_x`→`cloud.hint_state.x`；断言内容与期望值未动）。
- 棘轮下调：`test_shared_state_ratchet` `Cloud` 15→11；`test_module_size_ratchet` `pet_cloud.py` 1357→1353；`test_complexity_ratchet` `Cloud` 1111→1108。`architecture.md` 同步。

## 新增测试
`tests/test_pet_broadcast_state.py`：`CloudHintState` 默认值。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k pet_cloud leak_teardown pet_ui complexity` 648 条全过；`smoke_test.py --architecture` 413 条，仅已知环境红。
- 未运行：`--all --safe`。

## 回滚
`git revert` 本轮提交。

## 下一步
全量验收（`--all --safe`）并同步文档，再汇报合入安排。
