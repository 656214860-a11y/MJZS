# R925 UI 统一入口：文字层级（部分迁移）

- `qwen_setup.py` 的接口说明、计费说明和保存状态改用统一的说明／进度组件。
- `tts_settings.py` 的端点说明和保存／检测状态改用统一的说明／进度组件。
- 文字层级边界测试将两个已迁移设置页纳入组件导入与手写样式回退检查。

验证：

- `python tests/test_api.py`：54 条通过。
- `python tests/test_tts.py`：40 条通过。
- `python -m unittest tests.architecture.test_text_component_boundary`：2 条通过。
- `python smoke_test.py`：待本轮最终执行。

范围说明：文字层级尚未完成全量页面迁移，本轮不将该路线图项标记完成。
