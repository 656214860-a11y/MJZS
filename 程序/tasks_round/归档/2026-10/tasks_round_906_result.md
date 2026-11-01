# R906 UI 统一入口：Seedream 设置窗按钮

- Seedream 火山 API 设置窗的保存操作已使用 `PrimaryButton`；删除模型、检查配置、测试连接、打开控制台和取消已使用 `SecondaryButton`。
- 不改变模型档案、连接探测或外部网页打开的既有业务行为。
- 按钮边界测试覆盖增至七个已迁移表单，防止此设置窗退回裸 `ttk.Button`。
- 验证：源码编译、Seedream 定向回归、按钮边界测试及默认 smoke test 通过。
- 全站按钮覆盖尚未完成，路线图仍在推进。
