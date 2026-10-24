# R2032 结果：修复后台回调异常 'AutoState' 无 gate_auto_due（修复轮）

## 现象
状态栏反复出现「后台任务回调异常，已忽略：'AutoState' object has no attribute 'gate_auto_due'」，半自动／全自动待办裁决一直不跑。

## 根因
R2017 把 62 个 `auto_*` 属性迁进 `desktop_auto_state.AutoState`，`_poll_auto_due` 从此在 `self.auto` 上读写到期字段。`gate_auto_due`／`gate_auto_error` 的名字不是 `auto_` 开头，迁移时漏掉了，还留在 Desktop 上。结果 `_tick_auto_gates` 每一拍都抛 AttributeError。旧测试的假调度器从不调用 `due_at`，所以没测出来。

## 改动
- `desktop_auto_state.py`：AutoState 新增 `gate_due: int = 0`、`gate_error: str = ''`。
- `desktop.py`：删除 `self.gate_auto_due`／`self.gate_auto_error` 的初始化。
- `desktop_auto_flows.py`：`_tick_auto_gates` 改用 `'gate_due'` 和 `self.auto.gate_error`。
- `tests/test_core.py`：假调度器现在会真的调用 `due_at()`／`set_due(1)`，这样能复现本缺陷；断言改为检查 `desk.auto.gate_error`／`desk.auto.gate_due`。
- 契约有意变更（断言没有放宽）：
  - `tests/test_desktop_auto_state.py`：字段数 62→64。
  - 棘轮按实际值下调：complexity Desktop 1214→1212；shared_state Desktop 42→41。

## 验证（本轮实跑）
- `run_selftests.py -k test_core auto_state auto_flow automation`：ALL TESTS PASSED。
- `smoke_test.py --architecture`：一共 410 项，有 3 项红。这 3 项与本轮无关，属于已知遗留，修复前就是红的：
  - agents_md：缺少基准历史.json
  - round_baselines
  - skill_reference_injection
