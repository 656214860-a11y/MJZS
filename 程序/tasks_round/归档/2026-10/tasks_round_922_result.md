# R922 UI 统一入口：Tooltip 与弹窗创建全量审计

- 保留 SKILL 名称提示使用统一 `Tooltip` 的语义回归。
- 新增递归生产扫描，业务模块不得直接创建 `tk.Toplevel`；统一组件与主题适配器是仅有豁免。

验证：

- `python -m unittest tests.architecture.test_tooltip_boundary`：2 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

快捷键、文本层级、图标、滚动条及其它路线图覆盖率仍待审计。
