# R1774：修复轮——托盘右键菜单改用 Win32 TrackPopupMenu，修图标消失

1. 本轮类型：§3.2 修复轮。最小化到托盘后右键，托盘图标消失。

2. 测试跑了吗、三个基线过了吗：
   - 新增 tests/test_desktop_tray.py::test_menu_commands_dispatch_to_callbacks（mock TrackPopupMenu 验证恢复/退出分发）；test_desktop_tray 3/3。
   - 默认冒烟 8/8。
   - 完整安全全量：未跑（改动仅托盘弹菜单路径，未命中 §5 强制条件；全量由 post-commit 后台补跑）。

3. project_status.md 欠账少了吗：本轮改源码 +1（desktop_tray.py），全量欠账由后台补跑清账。

## 根因
托盘右键弹菜单原用 Tk `tk_popup`，依赖主窗状态与 Tk 的 grab；主窗处于 withdrawn（最小化到托盘）时 `tk_popup` 行为异常，菜单僵住、Shell 移除了托盘图标。

## 修复
改用 Win32 `CreatePopupMenu`＋`AppendMenuW`＋`TrackPopupMenu`（`TPM_RIGHTBUTTON|TPM_RETURNCMD|TPM_NONOTIFY`），弹菜单前 `SetForegroundWindow`（让菜单在点别处时正确收起），结束后 `DestroyMenu`＋`PostMessageW(WM_NULL)` 收尾；命令按返回的 ID 分发到恢复／强制重启／退出。不再依赖主窗是否 mapped/withdrawn。

## 校验
- 断言未动：仅新增 1 条 mock 分发测试，未改既有断言。

## 独立验收（advisor，主树真实环境直接运行）

- 范围：desktop_tray.py（_show_menu 改用 CreatePopupMenu/AppendMenuW/TrackPopupMenu/SetForegroundWindow/PostMessageW）、tests/test_desktop_tray.py（新增 mock 分发测试）。
- diff 审查：TrackPopupMenu 用 TPM_RIGHTBUTTON|TPM_RETURNCMD|TPM_NONOTIFY，弹前 SetForegroundWindow、结束 DestroyMenu＋WM_NULL；命令按 ID 分发恢复/强制重启/退出，不再依赖主窗 mapped 状态。
- 测试：test_desktop_tray 3/3（含 mock 分发）；冒烟 8/8。
- 断言未动：仅新增 1 条 mock 测试，未改既有断言。
- 说明：TrackPopupMenu 会阻塞等用户点选，真机右键弹菜单/图标不消失仍需重启后你实测确认。
