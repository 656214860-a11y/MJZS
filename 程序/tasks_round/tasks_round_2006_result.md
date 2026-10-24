# R2006 Pet 播报状态下沉 PetBroadcastState（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J5**。日期：2026-10-24。
基线：`codex/wip-R2001` @ ded11f16。零行为变更。

轮次类型：结构治理轮·执行（AGENTS.md §3.3）。三套基线：架构门禁仅剩 3 条已知历史红（`test_agents_md`、`test_round_baselines`、`test_skill_reference_injection`）；默认冒烟 8/8；覆盖率基线同步（315→316 模块）。债务：`--all --safe` 欠账 +1；Pet 共享状态上限 64→59。

## 改动

- 新增 `pet_broadcast_state.py`（L3，无 Tk）：`PetBroadcastState` 持有 `notice`／`last_status`／`announced`／`last_broadcast`／`held_broadcast`／`advance_at`；判重（`remember_status`、`is_repeat`、`spoke`、`forget_spoken`、`new_failure_batch`）、压住（`hold`、`take_held`）、推进节流（`advance_throttled`、`mark_advance`、`reset_advance`）只经这些方法写。`PetBroadcastAliasesMixin` 把旧属性名（含 `_last_broadcast` 等）转发到 `Pet.bstate`，既有调用方与用例不用改；`bstate` 缺失的半成品 Pet 首次访问补默认状态。
- `pet_ui.py`：`Pet.__init__` 改建 `self.bstate`，删四处散落初值；`pet_ui_voice.py`、`pet_ui_view.py`、`pet_ui_stages.py` 的 `say`／`broadcast`／招呼重置／`speech_blocked`／失败批次判重／snooze／unsnooze／`say_held`／推进节流改调状态方法。
- 偏差：`notice`（约 80 处写入）与 `last_status`（状态栏原文）写入面太宽，仍走旧属性名转发，没有逐处改成方法；任务单「只有一个 Mixin 写」在这两项上未做到，只做到判重／压住／节流四类的收口。
- 测试与登记：新增 `tests/test_pet_broadcast_state.py`；`_layers.py` 登记 L3；`test_shared_state_ratchet` Pet 64→59；覆盖率基线（316 模块，`pet_ui`／`pet_ui_stages`／`pet_ui_view`／`pet_ui_voice` 行数校正）与 `runbook.md` §11（316、266）；`architecture.md` 登记。

## 验证（本轮实测，经 gui_hidden）

- 定向 `-k pet_broadcast_state pet_ui sanhu_mode`：618 条，6 条红；同一批 `pet_ui` 在干净 HEAD（临时 worktree）同样 6 条红（5 条登录账号门禁拦截 + `test_the_cloud_stands_left_of_the_pet...` 几何），与本轮改动无关。
- `smoke_test.py --architecture`：410 条，仅 3 条已知红。
- 默认 `smoke_test.py`：8 项通过。
- 未跑 `--all --safe`，欠账 +1。未在真实窗口目测宠物播报。
- **断言未动**。

## 回滚

撤回 `pet_ui*.py` 四个文件、`runbook.md`、`architecture.md`、覆盖率基线、两个架构测试登记；删除 `pet_broadcast_state.py` 与其测试。

## 下一步

J6 Cloud 定位任务（`_position_job`／`_position_callback` 只由 CloudPlaceMixin 写，`pet_cloud_timing.py` 调其方法）。
