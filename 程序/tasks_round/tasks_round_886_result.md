# R886 UI 统一入口覆盖：下拉框样式审计

- `pet_models_ui.py` 不再定义私有 `ModelManager.TCombobox`，所有下拉框共享 `setup_styles()` 的全局 `TCombobox` 样式。
- 静态门禁扫描根目录业务模块，禁止 `Combobox` 样式覆盖，并要求桌面根窗口初始化统一样式。
- 验证：Combobox 门禁 2 条／0 红；`pet_models_ui.py` 语法检查通过。
