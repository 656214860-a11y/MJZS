# R2313 结果：拆 workflow_settings（J 路线后续 #6，重构轮）

## 改动（行为不变）
- 新增 `store_program_locator.py`（L1）：商店包定位 `store_package_program`、版本漂移纠正 `current_store_program`、Claude Desktop 图形程序判断 `gui_claude_program` 与 `GUI_CLAUDE_CLI_HINT`，原样迁出，只依赖标准库与 `platform_tools`（懒导入）。
- `workflow_settings` 在文件头重新导出这四个名字；`find_program`、`find_model_program` 仍在原处按名字取用，所以 `patch('workflow_settings.store_package_program')`、`patch.object(settings,'find_program')` 等补丁点全部保留。`find_program` 要懒导入 L3 的 `qwen_adapter`，不迁。
- `workflow_settings.py` 1069 → 994 行，低于 1000，从 `test_module_size_ratchet.OVERSIZE_CAPS` 删除登记。
- 层级登记、覆盖率基线（352 模块，未覆盖 299）、`runbook.md` §11 数字同步。

## 验证
- `run_selftests -k claude_program_detection workflow model_pool opencode_engine environment_check layers coverage_baseline module_size pet_ui skills`：1027 条，0 个文件有红。
- `smoke_test.py --architecture`：全绿（临时拷入 `基准历史.json`，用后已删，未入库）。
- 未跑全量。断言未动。
