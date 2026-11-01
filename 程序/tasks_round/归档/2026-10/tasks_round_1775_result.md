# R1775：修复轮——托盘最小化／点击托盘闪退（改为独立线程隐藏窗口，不再子类化 Tk 主窗）

1. 本轮类型：§3.2 修复轮。用户报告：最小化时软件闪退，点击系统托盘无法启动，右键托盘闪退。

2. 测试跑了吗、三个基线过了吗：
   - 定向 `run_selftests.py -k desktop_tray`：4/4（含新增子进程回归用例）。
   - 默认冒烟 8/8；`smoke_test.py --affected desktop_tray` 9/9。
   - 架构门禁 375 条：本轮前 HEAD 上有 4 条由 R1773 带入的红（直接 Popen 越界 1、覆盖率审计 21 两条、skip 台账 1），本轮全部收口；剩余 1 错 1 败均为工作树环境缺文件（见「未通过项」），主检出与 `.wt/ci` 干净检出不受影响。
   - 真实应用实测：从工作树启动完整程序，另起进程用 `ShowWindowAsync(SW_MINIMIZE)` 最小化、向托盘窗口投递左键单击，4 轮全部「最小化→收进托盘→点击恢复」，进程全程存活，`WM_CLOSE` 后正常退出码 0。
   - 完整安全全量：本轮改了启动路径模块，合入 master 后由 `scripts/auto_full_safe.py --run` 补跑（见 project_status 验证基线）。

3. project_status.md 欠账少了吗：本轮改源码 +1（desktop_tray.py）；全量欠账由合入后补跑清账，未跑前不写通过。

## 根因（实测证据）

R1773 用 `SetWindowLongPtrW(GWL_WNDPROC)` 把 Python 回调子类化到 Tk 主窗上。此后主窗**每一条**窗口消息都经过 ctypes 回调，回调里再经 `CallWindowProcW` 转给 Tk。ctypes 调外部函数时会自己释放 GIL，Tk 在其中处理最小化产生的 `<Unmap>` 等事件时回调 Python 绑定，`_tkinter` 取不到它记录的线程状态，解释器直接 `Py_FatalError`，进程以 `0xC0000409` 终止。托盘点击回调里调 `after_idle` 是同一类重入。R1774 只换了菜单实现，没碰这条根因。

- 用户机器的 Windows 应用程序事件日志：2026-10-21 05:03、05:08、05:09、05:19 共 4 次 `pythonw.exe` 崩溃，异常码 `0xc0000409`，故障模块 `ucrtbase.dll`，均在 R1773／R1774 版本启动之后。
- 改动前复现（独立脚本，HEAD 版 `desktop_tray.py`）：

```
Fatal Python error: PyEval_RestoreThread: the function must be called with the GIL held, after Python initialization and before Python finalization, but the GIL is released (the current Python thread state is NULL)
```

- 先红后绿：新增回归用例的子进程脚本跑 HEAD 版 `desktop_tray.py`，退出码 `3221226505`（＝`0xC0000409`，与用户事件日志一致），并打印上面的 Fatal；跑本轮版本退出码 0，输出 `STATES=withdrawn,normal,withdrawn,normal,withdrawn,normal`。

## 修复

`desktop_tray.py` 重写线程模型：

- 托盘图标挂在**独立线程**创建的隐藏原生窗口（类名 `DramaStudioTrayWindow`）上，该线程跑自己的 `GetMessage` 循环；Tk 主窗不再被子类化。
- 托盘线程的窗口过程只做两件事：左键／双击把「恢复」命令入队；右键在托盘线程里弹 Win32 `TrackPopupMenu`，把选中的命令入队。它不调用任何 Tk 接口。
- Tk 主线程用 `after(TRAY_POLL_MS=120)` 定时排空队列，在正常事件循环里执行恢复／强制重启／退出。
- `remove()` 投递 `WM_CLOSE` 给托盘窗口：托盘线程删图标、销毁窗口、退出消息循环，主线程 `join` 收摊。
- 用私有 `ctypes.WinDLL('user32'／'shell32'／'kernel32', use_last_error=True)` 实例补齐 64 位句柄的 argtypes／restype，不再改全局 `ctypes.windll.user32` 的函数原型（避免影响其它模块）；修正 `GetModuleHandleW` 返回值被按 32 位截断。
- `force_restart` 改走 `platform_tools.launch_background`（平台层统一后台进程入口），消除直接 `subprocess.Popen` 越界；托盘「强制重启」先摘图标再退出，不留幽灵图标。
- `PYTHONW` 优先取当前解释器旁的 `pythonw.exe`，其次仓库随附路径（工作树内也能解析）。

## 测试与台账

- `tests/test_desktop_tray.py`：
  - `test_add_and_remove_tray_icon`：新增断言「托盘窗口句柄不等于 Tk 窗口」与「移除后托盘线程已收摊」；原断言保留。
  - `test_menu_commands_dispatch_to_callbacks`：契约有意变更——菜单在托盘线程只入队，命令由 Tk 侧 `_drain` 分发，故在两次 `_show_menu` 后补一次 `_drain`；**断言未动**（仍为 `['restore', 'quit']`）。
  - 新增 `TrayMinimizeCycleTests.test_minimize_and_click_tray_cycles_without_crash`：子进程里 3 轮最小化／点击托盘，断言退出码 0 与状态序列。放子进程是因为旧实现会直接带崩测试进程。
- `tests/skip_reasons.py` 新增 `PLATFORM_WINDOWS_ONLY`；`维护记录/skip台账.json` 登记托盘测试的 skip，并补登 `tests/test_skill_panel_production_locks.py::WorkflowLockEnablementTests.setUp` 一条早已存在但漏登的 `PLATFORM_TK_DISPLAY`（只登记，不改该测试）。

## 未通过项（环境原因，非本轮引入）

- `test_agents_md.test_performance_history_is_declared_as_historical_only`：工作树缺 `程序/维护记录/基准历史.json`（`.gitignore:59` 排除）；主检出存在。
- `test_skill_reference_injection.test_script_stages_name_only_their_approved_00_references`：`程序/skills/00全流程SKILL/AIGC创作全流程` 是 gitlink（mode 160000），工作树里为空目录；主检出存在。

## 仍需用户确认

- 托盘右键菜单的真机交互（右键弹出、点别处收起、选「强制重启」）已在脚本里用 ESC 收起菜单验证不崩，但菜单项点选与强制重启后自动拉起，需要你重启应用后亲手试一次。

## 提交

- 已在分支 `claude/project-handoff-f6eb50` 提交，随后快进合入 master；commit hash 见 git log `R1775:`。
