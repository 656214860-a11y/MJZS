# R1833 结果：ui_theme.install_window_placement 提出模块级辅助函数（整理轮）

- 改动：`install_window_placement` 里不靠闭包状态的五个辅助函数提到模块级：`_grab_popup`、`_release_popup_on_unmap`、`_focus_popup`、`_work_area(window, root)`、`_cancel_position_job`；函数体原样保留，用到 `tk.TclError` 的地方补了局部 `import tkinter as tk`。函数从 224 行降到 147 行；`OVERSIZE_CAPS` 删除该条。（这里含嵌套 class，c2c 处理不了，所以手工提取。）
- 差分测试先行：`tests/test_window_placement_equivalence.py`，旧实现取 HEAD 原文内嵌。它会改写全进程的 `tk.Toplevel.__init__`，所以新旧实现各开一个子进程跑同一段脚本：主窗、带子控件的弹窗、隐藏再显示、定位前就销毁、无边框窗。逐步对照几何、透明度、grab、minsize、transient、绑定、定位任务和失败提示，并对照子进程的 stderr。旧实现自比为绿。
- 变异检验：`_grab_popup` 的 `grab_set` 改成 `grab_release`，差分测试变红，已还原。
- 验证（本轮运行，隐藏桌面）：差分测试、test_timers、test_ui_style_engine、test_ui_theme、test_ui_widgets_dialogs 共 45 项通过；`run_selftests.py --architecture` 通过。
- 断言未动。
