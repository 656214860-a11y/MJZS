# R2015 Pet 四个下划线旧名退役（结构治理轮·契约）

来源：`CONTRACT_forwarding_retire.md` 结论第 1 步。日期：2026-10-25。基线：`codex/wip-R2013` @ 56d611b4。

轮次类型：结构治理轮·契约（行为零变化）。三套基线：默认冒烟 8/8；架构门禁 `smoke_test.py --architecture` 只剩 3 条已知红（`test_agents_md` ERROR、`test_round_baselines`、`test_skill_reference_injection`）；覆盖率基线不变（`pet_broadcast_state` 69、`pet_ui_stages` 871 可执行行均未变）。债务：`--all --safe` 欠账 +1。

## 改动

- `pet_broadcast_state.py`：`PetBroadcastAliasesMixin` 只转发公开属性 `notice`／`last_status`，退役 `_announced`／`_last_broadcast`／`_held_broadcast`／`_advance_at` 四个下划线旧名；`bstate` 缺失时仍首次访问补默认状态。
- `pet_ui_stages.py`：仅一处 docstring 指向 `bstate.last_broadcast`。
- `tests/test_pet_ui.py`（14 行）、`tests/test_sanhu_mode.py`（4 行）：访问路径 `pet._x` → `pet.bstate.x`。
- `tests/test_pet_broadcast_state.py`：别名用例改为公开名转发＋懒建状态，并新增「旧下划线名已不存在」用例。
- `architecture.md`：同步 pet_broadcast_state 一句。

## 验证（本轮实测，经 gui_hidden）

- `-k pet_broadcast_state`：7 条全绿。
- `-k pet_ui sanhu_mode`：只剩干净 HEAD 就红的 6 条（`test_pet_ui` 5 条登录闸门＋1 条云朵几何），与本轮无关。
- **断言未动**：测试里只改访问路径；`test_pet_broadcast_state` 的别名用例按新契约重塑（旧名由「转发」改为「不存在」）。

## 回滚

回退本轮提交。
