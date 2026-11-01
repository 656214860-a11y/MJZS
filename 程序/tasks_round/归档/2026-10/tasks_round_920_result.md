# R920 UI 统一入口：文件选择全量审计

- 文件选择边界测试扩展为递归扫描生产模块。
- `ui_dialogs.FileDialog` 是唯一允许直接调用 tkinter 文件选择器的实现位置；业务模块统一经 `FileDialog` 处理取消与异常。

验证：

- `python -m unittest tests.architecture.test_file_dialog_boundary`：5 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

快捷键、文本层级、下拉框及其它路线图覆盖率仍待审计。
