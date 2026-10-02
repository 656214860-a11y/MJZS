# R514 结构治理轮：后台模型报告空正文拦截

- Claude 与 Qwen 后台引擎在响应 JSON 已安全发布后，均须验证最终制作报告非空才覆盖正式报告；空结果保留响应记录并抛出明确错误。
- 验证：`tests.test_workflow tests.test_force_quit` 91/91，编译通过，默认冒烟 8/8；架构门禁 `smoke_test.py --architecture` 91/91。
- 未修改用户项目数据、密钥或界面。
