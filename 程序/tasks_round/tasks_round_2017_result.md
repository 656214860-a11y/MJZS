# R2017 AutoState 62 个 auto_* 旧属性名转发退役（结构治理轮·契约）

来源：`CONTRACT_forwarding_retire.md` 结论第 2 步。日期：2026-10-25。基线：`codex/wip-R2015`（b4b28621）。

轮次类型：结构治理轮·契约（行为零变化）。三套基线：默认冒烟 8/8；架构门禁 `smoke_test.py --architecture` 只剩 3 条已知红（`test_agents_md` ERROR、`test_round_baselines`、`test_skill_reference_injection`）；覆盖率基线同步 4 个模块的可执行行数（`desktop_auto_state` 104→93、`desktop_auto_flows` 536→537、`desktop_pet_bridge` 100→101、`page_navigation_controller` 58→61），`test_coverage_baseline` 5 条绿。债务：`--all --safe` 欠账 +1。

## 改动

- `desktop_auto_state.py`：删 `legacy_name`／`_Forward` 及 62 个旧名描述符；`AutoStateAliasesMixin` 改名 `AutoStateHolderMixin`，只保留 `auto` 缺失时懒建默认状态；新增 `flow_slot`／`flow_get`／`flow_set`（流程名 `auto_<流程>` → `self.auto.<流程>_<后缀>`，`cloud_monitor` 仍在窗口上）。
- `desktop_auto_flows.py`：`_poll_auto_due` 的 due／busy 字段名改作用在 `self.auto`，8 个调用点去掉 `auto_` 前缀；`_stop_expired_auto`、`kick_unattended` 经 `flow_get/flow_set`。
- `desktop_pet_bridge.py`：`pet_advance` 经 `flow_get/flow_set`。
- `page_navigation_controller.py`：`LIFECYCLES` 拆成窗口级两个＋`AUTO_LIFECYCLES`（从 `owner.auto` 取），取消顺序不变。
- `desktop.py`：导入与基类改名。
- 测试：`.auto_X`→`.auto.X`、`._auto_X_ticket`→`.auto.X_ticket` 共 228 处（`test_ui_edges` 149、`test_pet_ui` 38、`test_req_s07_anchors` 28、`test_desktop_automation_service` 12、`test_core` 1）；`desktop_stub` 加 `auto=` 参数，矩阵用例用 `slot/read/write` 取代 getattr/setattr；`test_desktop_auto_state` 的转发用例改为「旧名已不存在」＋懒建用例；`test_page_navigation_controller` 加 `owner.auto` 替身与「无 auto」用例。
- `architecture.md` 同步；顺带删除 R2015 提交误带入的 `tasks_round_2014_result.md`（R2014 属另一分支）。

## 验证（本轮实测，经 gui_hidden）

- `-k ui_edges pet_ui sanhu_mode desktop_auto_state desktop_automation_service page_navigation desktop_pet`：764 条，只剩干净 HEAD 就红的 6 条 `test_pet_ui`（5 条登录闸门＋1 条云朵几何）。
- `-k desktop_auto_state desktop_automation_service page_navigation req_s07 core`：182 条全绿。
- 中途发现生产里还有 `name + '_due'` 拼接式取名（`pet_advance`／`kick_unattended`／`_stop_expired_auto`），首轮因此多出 6 条红，已由 `flow_*` 修掉。
- **断言未动**：测试里只改访问路径、桩构造方式与取名辅助；全部 `assert*` 的期望值原样。转发用例按新契约重塑（旧名由「转发」改为「不存在」）。

## 回滚

回退本轮提交。
