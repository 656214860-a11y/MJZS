# R902 UI 统一入口：资产参考图导入按钮

- 资产参考图导入窗的“选择图片、保存、删除参考图、取消”均从裸 `ttk.Button` 改为 `PrimaryButton`／`SecondaryButton`。
- 保存是唯一主操作；选择、删除与取消为次操作，既不改变删除确认和回收语义，也保留原有布局。
- 新增 `tests/architecture/test_button_boundary.py`，锁定该已迁移表单不再直接构造 `ttk.Button`。
- 验证：`py_compile asset_reference_import.py` 通过；按钮边界测试 1 条／0 红。
- 全站按钮覆盖尚未完成，路线图仍在推进。
