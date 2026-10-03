# R915 UI 统一入口：应用页语义按钮

- 视频提示词的“ MCP 优化”保留既有高亮样式，改由 `PrimaryButton` 承载，仍显式提示付费调用层级。
- 离线“生成编剧任务书”改由 `PrimaryButton` 承载；既有离线生成回调不变。
- 按钮边界测试纳入 `app.py`，禁止重新引入裸 `ttk.Button`。

验证：

- `python -m py_compile app.py` 通过。
- `python -m unittest tests.architecture.test_button_boundary`：17 条通过。
- `python tests/test_app_shortcut.py`：37 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

主壳 `desktop.py` 的按钮入口及路线图其它项目仍待完成。
