# R929 UI 统一入口：复制写入审计

- 复制写入门禁从根目录扫描升级为递归生产扫描。
- `clipboard_append` 仅允许出现在 `prompt_window.copy_text`；该入口持有剪贴板锁、统一错误返回并提供脱敏预览。
- SKILL 示例脚本、测试、维护和轮次资料不属于产品生产代码，明确排除。

验证：

- `python -m unittest tests.architecture.test_copy_entry_boundary`：2 条通过。
- `python smoke_test.py`：8 项通过、0 失败。
