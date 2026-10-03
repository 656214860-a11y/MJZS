# R916 UI 统一入口：主壳语义按钮

- `desktop.py` 的所有裸 `ttk.Button` 已替换为 `PrimaryButton` 或 `SecondaryButton`。
- 导航、资产清单、目录和链接仍显式保留原有样式；阶段启动、目录认领、项目创建与进入、视频模式入口保持主操作层级。
- 按钮边界测试纳入主壳。生产代码中，`ttk.Button` 仅存在于 `ui_widgets.py` 的统一组件实现。

验证：

- `python -m py_compile desktop.py` 通过。
- `python -m unittest tests.architecture.test_button_boundary`：18 条通过。
- `python tests/test_stage_wiring.py`：16 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

按钮入口虽已完成裸控件清理，UI 路线图的文本、通知、忙碌态等范围仍需逐项审计。
