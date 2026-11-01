# R1773：功能轮——最小化到系统托盘 + 右键菜单（恢复／强制重启／退出）

1. 本轮类型：§3.1 功能轮。新增「最小化到系统托盘 + 右键菜单（恢复窗口／强制重启／退出）」，零第三方（ctypes Shell_NotifyIcon）。

2. 测试跑了吗、三个基线过了吗：
   - 新增 tests/test_desktop_tray.py：托盘图标添加/移除、重启路径解析 2 用例 OK（真实 Shell_NotifyIcon 增删 + WNDPROC 子类化）。
   - 架构门禁：test_layers／function_size_ratchet／coverage_baseline／static_hygiene／requirement_traceability 21 项 OK。
   - 默认冒烟 8/8。
   - 完整安全全量：未跑（新增 UI 部件，未命中 §5 强制条件；全量由 post-commit 后台补跑）。

3. project_status.md 欠账少了吗：本轮改源码 +1（desktop_tray.py、desktop.py），全量欠账由后台补跑清账。

## 根因与实现
- Tkinter 无内置托盘：最小化默认进任务栏（底部），不是系统托盘（右下角）。新增 `desktop_tray.py`（L4）用 ctypes 调 Win32 `Shell_NotifyIcon`，子类化主窗 WNDPROC 捕获托盘点击。
- 点 ✕ 默认关闭：沿用既有 `WM_DELETE_WINDOW → close()`，未改。
- 最小化到托盘：绑定 `<Unmap>`，窗口进入 iconic 态时 `withdraw()` 收进托盘；`<Destroy>` 兜底移除托盘图标（防测试/非正常销毁留幽灵图标）。
- 强制重启＝杀进程重开：先派一个脱离的辅助进程睡 0.8 秒再拉起启动器（`pythonw -I 启动漫剧制作助手.pyw`），再 `os._exit(0)`，避开启动器单实例互斥量竞态。
- 托盘菜单：恢复窗口 / 强制重启 / 退出。

## 校验与契约
- 新模块登记：`desktop_tray` 登记 L4（tests/architecture/_layers.py）；覆盖率基线刷新为 292 模块（+1）；runbook §11 模块数同步 291→292。
- 断言未动：仅新增 1 个测试文件，未改既有断言。

## 独立验收（advisor，主树真实环境直接运行）

- 范围：desktop_tray.py（新 L4：TrayIcon + force_restart + TrayMixin）、desktop.py（接入 TrayMixin）、tests/test_desktop_tray.py（新）、tests/architecture/_layers.py（登记）、维护记录/覆盖率基线.json（刷新 292）、runbook.md（291→292）。
- diff 审查：Shell_NotifyIcon 结构体/常量正确；WNDPROC 子类化转发非托盘消息、持有引用防 GC；最小化仅拦 iconic 态；强制重启用脱离辅助进程避开单实例互斥量。
- 测试：test_desktop_tray 2/2（真实增删托盘图标）；test_layers／function_size_ratchet／coverage_baseline／static_hygiene／requirement_traceability 21 项；冒烟 8/8；Desktop 创建类用例（writing_page、idea_chat 发送流程）3 项通过。
- 断言未动：仅新增 1 个测试文件，未改既有断言。
- 说明：托盘菜单跑在 Tk 主线程，主线程真卡死时菜单也不响应；强制重启覆盖「界面还活着」的重启需求，真死场景仍需修根因。
