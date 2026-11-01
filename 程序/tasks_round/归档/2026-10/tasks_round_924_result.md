# R924 UI 统一入口：文字层级（部分迁移）

- `agent/prompt_optimizer.py` 的多段费用与隐私说明改用 `DescriptionBlock`。
- `seedream_settings.py` 的使用说明、模型说明改用 `DescriptionBlock`，保存状态改用 `ProgressLabel`。
- 文字层级边界测试登记上述页面与所需语义组件，并禁止迁移页面回退为手写字体／颜色。

验证：

- `python tests/test_mcp_settings.py`：8 条通过。
- `python tests/test_seedream_direct.py`：9 条通过。
- `python -m unittest tests.architecture.test_text_component_boundary`：2 条通过。
- `python smoke_test.py`：待本轮最终执行。

范围说明：文字层级尚未完成全量页面迁移，本轮不将该路线图项标记完成。
