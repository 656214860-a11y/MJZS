# R921 UI 统一入口：下拉框样式全量审计

- `TCombobox` 样式门禁由根目录扩展为递归生产模块扫描。
- 桌面根窗口仍负责调用 `ui_widgets.setup_styles()`；业务模块不得私自覆盖 Combobox 视觉。

验证：

- `python -m unittest tests.architecture.test_combobox_boundary`：2 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

快捷键、文本层级、图标、滚动条及其它路线图覆盖率仍待审计。
