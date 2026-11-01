# R2009 Cloud 定位重试登记归 CloudPlaceMixin（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J6**。日期：2026-10-25。
基线：`codex/wip-R2006` @ bf884a09。零行为变更。

轮次类型：结构治理轮·执行（AGENTS.md §3.3）。三套基线：架构门禁仅剩 3 条已知历史红；默认冒烟 8/8；覆盖率基线行数校正（模块数不变，316）。债务：`--all --safe` 欠账 +1；Cloud 类行数上限 1115→1113，Cloud 共享状态上限 18→15。

## 改动（无新模块）

- `pet_cloud_place.py` 的 `CloudPlaceMixin` 新增三个方法并独占 `_position_job`／`_position_callback`／`_position_retries` 的写入：`_reset_position_state`（初值）、`_arm_position_retry`（原 `_place_window` 里排重试票的整段，含闭包与上限）、`_take_position_job`（清登记并交出旧 after 句柄）。
- `pet_cloud.py` 的 `Cloud.__init__` 改调 `_reset_position_state`；`pet_cloud_timing.py` 的 `_cancel_position` 改经 `_take_position_job` 取句柄后自行 after_cancel，不再直接写这两个字段。
- 测试与登记：新增 `tests/test_pet_cloud_position_state.py`（7 条）；`test_complexity_ratchet` Cloud 1115→1113；`test_shared_state_ratchet` Cloud 18→15；覆盖率基线 `pet_cloud`／`pet_cloud_place`／`pet_cloud_timing` 行数校正。

## 验证（本轮实测，经 gui_hidden）

- 定向 `-k pet_cloud cloud pet_ui_view`：57 条全绿（含既有 `test_pet_cloud_contract` 定位重试用例）。
- `smoke_test.py --architecture`：仅 3 条已知红（`test_agents_md`、`test_round_baselines`、`test_skill_reference_injection`）。
- 默认 `smoke_test.py`：8 项通过。
- 未跑 `--all --safe`，欠账 +1。未在真实窗口目测云朵定位。
- **断言未动**。

## 回滚

撤回 `pet_cloud.py`、`pet_cloud_place.py`、`pet_cloud_timing.py` 与两个棘轮、覆盖率基线的改动，删除新增测试。

## 下一步

J7 行数上限（可选）；契约轮（AutoState／PetBroadcast 旧属性名转发是否退役）；launch_comfy mock 同步测试轮。
