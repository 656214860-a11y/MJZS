# R489 验证/基线轮：全量回归收口

## 轮次结论

- 本轮是验证/基线轮，执行来源：`tasks_round/tasks_round_488_result.md` 的 I 与 J1；未修改产品代码或测试文件。
- 测试已运行且三个基线均通过：默认冒烟 8/8；架构层 82/82；完整安全回归 3,209 条、817.5 秒、0 个失败文件。
- `project_status.md` 欠账已减少：R486--R487 的“全量基线未复验”待办已由本轮全量安全回归收口；本轮不更新状态文件，遵守每五实际轮次更新一次的节奏。

## I / J1 执行记录

1. `run_selftests.py --layer architecture --all`
   - 49 个测试文件、82 条用例、3.3 秒、0 个文件有红。
   - 最慢单元：`architecture.test_completion_gate`，2.3 秒。
2. `run_selftests.py --layer service --all`
   - 1,482 条用例、25.2 秒、0 个文件有红。
   - 最慢单元：`test_copy_rules`，24.2 秒。
3. `run_selftests.py --layer gui-e2e --safe --all`
   - 662 条用例、261.7 秒、0 个文件有红。
   - 最慢单元：`test_ui_edges#14`，36.7 秒。
4. `run_selftests.py --all --safe`
   - 3,209 条用例、817.5 秒、0 个文件有红。
   - 最慢 10 单元：`test_ui_edges#14` 34.1 秒、`test_perf_baseline` 27.5 秒、`test_copy_rules` 20.3 秒、`test_ui_edges#12` 18.2 秒、`test_ui_edges#10` 15.5 秒、`test_ui_edges#7` 13.8 秒、`test_final_viewer` 13.5 秒、`test_asset_gating` 13.4 秒、`test_asset_detail#2` 13.3 秒、`test_ui_edges#11` 12.7 秒。
   - `维护记录/自检增量.json` 已成功刷新。
5. `smoke_test.py`
   - 8 项通过、0 项失败。

## J / K 决策

- J2 不触发：所有测得工作单元均低于 180 秒超时阈值；无失败或明显异常，故不改 fixture、外部进程或等待循环。
- J3 不触发：本轮在正常可写项目环境中成功刷新增量台账，未复现 R488 提到的台账写入失败。
- K1 已执行：未迁移任何测试文件，191 个测试模块的组织保持不变。K2/K3 仅在后续有独立迁移需求或实测性能问题时再执行。

## 自审

- 通过：验收要求的总用例数、总耗时、最慢单元、失败模块数和台账刷新状态均已记录。
- 通过：仅新增本轮结果文件；未改产品代码、测试逻辑、断言或用户项目数据。
- 通过：无越界依赖、无测试迁移、无新增代码问题。
