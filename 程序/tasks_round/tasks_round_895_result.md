# R895 UI 统一入口：阶段模型确认

- `stage_models._ask()` 默认使用 `ui_widgets.ask_confirmation()`，`ASKER` 测试注入保持原调用约定。
- 验证：`py_compile stage_models.py` 通过；`test_manual_gate` 15 条／0 红。
- 其他历史直接确认调用仍待迁移，路线图未完成。
