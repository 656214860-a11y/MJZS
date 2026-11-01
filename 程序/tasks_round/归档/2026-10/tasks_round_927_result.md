# R927 UI 统一入口：表格创建审计

- `DataTable` 结构门禁由根目录扫描升级为递归生产扫描。
- 全仓生产代码仅 `desktop.py` 保留 3 处裸 `Treeview`：侧栏项目选择、项目选择弹窗和项目主页；三者均为树形导航，不是业务数据表。
- 其它表格页面继续使用 `DataTable`，由其统一列宽、空态、选择、排序和滚动壳。

验证：

- `python -m unittest tests.architecture.test_data_table_boundary`：17 条通过。
- `python smoke_test.py`：8 项通过、0 失败。
