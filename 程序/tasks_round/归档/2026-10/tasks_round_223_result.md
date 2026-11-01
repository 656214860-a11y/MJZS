# Round 223 结果：分镜表格 UI 适配器拆分

## 改动文件

- `storyboard_table_ui.py`
- `storyboard_files.py`
- `tests/architecture/_layers.py`
- `architecture.md`

## 改动摘要

新增 L4 `storyboard_table_ui`，承接 Treeview 构建、列宽调整和目录行渲染；`storyboard_files` 保留同名导出，现有页面调用不变。

## 验证结果

- `test_column_fit` 与分层校验：18/18 通过。
- 默认 `smoke_test.py`：8/8 通过。
