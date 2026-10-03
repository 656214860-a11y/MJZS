# R919 UI 统一入口：右键菜单全量审计

- 右键菜单边界测试扩展为递归扫描生产模块。
- `ui_widgets.ContextMenu` 是唯一的业务菜单创建入口；统一承载菜单定位与 grab 释放。

验证：

- `python -m unittest tests.architecture.test_context_menu_boundary`：2 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

文件选择、快捷键、文本层级及其它路线图覆盖率仍待审计。
