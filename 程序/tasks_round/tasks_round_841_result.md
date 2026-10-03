# R841 结果：事件总线统一契约

- 收口路线图第二批第 5 项的现有实现边界：跨模块状态只经 `pet_bus.emit_safe()`；`pet_agent._emit()` 与 `pet_ui._emit()` 为仅有的受控转发器，直接 `Bus.emit()` 只能留在 L0 `pet_bus` 实现中。
- `broadcaster` 明确为用户可见文本日志，不得作为跨模块状态总线；静态门禁仅允许 `desktop` 与 `pet_ui` 调用它。
- 新增 `test_event_bus_boundary.py`，含直调总线、文本播报旁路的 AST 金丝雀；同步 `AGENTS.md` 硬约束、门禁清单和 `architecture.md`。未改产品代码或用户数据。

## 验证

- `run_selftests.py -k 'event_bus_boundary agents_md completion_gate coverage_audit_ratchet' --safe`：20 条／0 红。
- `python smoke_test.py`：8/8 通过；`python smoke_test.py --architecture`：226/226 通过。
- `run_selftests.py --all --safe`：3671 条／0 红（1005.4 秒）；路线图条目收口的完整安全回归已完成，`last_full_safe_all_round=R841`。
