# R905 UI 统一入口：设置窗按钮

- Comfy 云图片、Qwen Code 和 Prompt Optimizer 的设置窗已将保存操作改用 `PrimaryButton`，删除、检测及外部帮助链接改用 `SecondaryButton`。
- 保留既有保存、删除确认、连接测试和打开网页行为；清除了三处无用的 `messagebox` 导入。
- 按钮边界测试扩展为六个已迁移表单，并支持检查函数内局部导入的 UI 组件。
- 验证：三处源码编译、按钮边界测试及默认 smoke test 通过。
- 全站按钮覆盖尚未完成，路线图仍在推进。
