# R2144 结果：最小化留在任务栏，不再收进托盘（功能轮）

## 问题
用户反馈：窗口最小化后，任务栏上「漫剧制作助手」的图标下面没有其他应用那样的白点。
原因：`desktop_tray.TrayMixin.setup_tray` 给主窗绑了 `<Unmap>`，`_on_minimize_to_tray` 在最小化（state 为 iconic）时调用 `withdraw()`，窗口从任务栏消失，只剩托盘图标。任务栏上那只三虎是固定的快捷方式（目标 `pythonw.exe -I 启动漫剧制作助手.pyw`），没有运行中的窗口挂在它下面，所以没有白点。

## 改动
- `desktop_tray.py`：删掉 `<Unmap>` 绑定、`_on_minimize_to_tray` 和 `_tray_minimized`。最小化走系统默认，窗口留在任务栏。托盘图标和右键菜单（恢复窗口／强制重启／退出）不变，`restore_from_tray` 对最小化的窗口照常 `deiconify` + `lift`。模块与类的说明同步改写。
- `tests/test_desktop_tray.py`：最小化循环测试的期望状态由 `withdrawn,normal,…` 改为 `iconic,normal,…`。这是契约有意变更（最小化不再收进托盘），不是弱化断言；「不闪退、点托盘能恢复」的检查原样保留。

## 验证（本轮运行，worktree）
- `run_selftests -k desktop_tray pet_ui desktop_shell`（经 gui_hidden）：ALL TESTS PASSED；托盘相关 2 条因隐藏桌面没有任务栏宿主而跳过。
- 这 2 条在交互桌面用 unittest 单独跑 `test_desktop_tray`：7 条全部通过，含最小化循环测试。
- `smoke_test.py --architecture`：通过（临时复制被忽略的 `维护记录/基准历史.json`，跑完已删除）。
- 未在真实应用里手动最小化看白点。
