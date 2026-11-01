# R892 UI 统一入口：确认对话框第三批

- 模型删除确认已从 `asset_batch`、`cloud_video`、`qwen_setup`、`keyframe_comfy` 与 `agent.prompt_optimizer` 迁移至 `ask_confirmation()`。
- 这些调用都明确标记为危险确认，保留原来“取消即不删除”的同步控制流。
- 验证：五个模块 `py_compile` 通过；`test_mcp_settings` 8 条／0 红。
- 仍有其他业务模块的历史直接确认调用，路线图尚未完成。
