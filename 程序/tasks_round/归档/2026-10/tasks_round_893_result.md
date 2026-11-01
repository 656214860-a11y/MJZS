# R893 UI 统一入口：确认对话框第四批

- `asset_detail.delete_variant()` 与 `asset_reference_import` 的参考图解除绑定已使用 `ask_confirmation()`。
- 二者均为危险确认：取消、关闭或父窗销毁不会执行删除／解绑。
- 验证：模块语法检查通过；`test_asset_detail.VariantTests` 5 条／0 红。
- 其他业务模块的历史直接确认调用仍待迁移，路线图未完成。
