# R928 UI 统一入口：输入框创建审计

- 递归生产扫描确认不存在业务层 `tk.Entry`、`ttk.Entry`、`tk.Text` 或 `ttk.Text` 创建。
- 输入视觉与状态统一由 `LineInput`、`TextArea` 承担。
- 门禁显式排除测试、轮次记录、维护资料和缓存目录，确保结论只针对生产代码。

验证：

- `python -m unittest tests.architecture.test_input_boundary`：4 条通过。
- `python smoke_test.py`：8 项通过、0 失败。
