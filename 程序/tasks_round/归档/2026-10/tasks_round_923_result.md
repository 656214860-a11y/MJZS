# R923 UI 统一入口：滚动条样式全量审计

- 保留主题层对横、竖 `TScrollbar` 的共享 token 与 active 状态校验。
- 新增递归生产扫描：业务层建立标准 `ttk.Scrollbar` 时不得私设 style，统一继承全局主题。

验证：

- `python -m unittest tests.architecture.test_scrollbar_theme_boundary`：2 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

快捷键、文本层级、图标、复制与其它路线图覆盖率仍待审计。
