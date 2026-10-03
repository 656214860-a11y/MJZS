# R907 UI 统一入口：阶段调用设置按钮

- 阶段调用设置窗的文件选择、Qwen API、检查和取消已使用 `SecondaryButton`，保存已使用 `PrimaryButton`。
- 保留禁用 Qwen API 按钮、文件选择和保存配置等原有交互；清除无用的 `messagebox` 导入。
- 按钮边界测试覆盖增至八个已迁移表单，防止阶段配置窗退回裸 `ttk.Button`。
- 验证：源码编译、工作流定向回归、按钮边界测试及默认 smoke test 通过。
- 全站按钮覆盖尚未完成，路线图仍在推进。
