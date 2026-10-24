# R1976 结果（修复轮）

## 用户反馈
1. 悬停卡片（TreeRowCard）看不到完整文件信息框。
2. 按住标题栏拖窗时三虎突然弹窗，拖动被打断。

## 根因（推断，隐藏桌面无法用真实指针复现）
1. `ui_theme.install_window_placement` 给每个新 Toplevel 绑 `<Map>`→`grab_set`、置 `-alpha 0` 并重新居中；Tooltip 浮层因此抓 grab，鼠标仍停在表格上被判「离开」，卡片刚出现就被自己收掉。
2. 云朵自动播报（focus=False）在 Windows 拖窗模态循环中仍由 Tk 定时器触发 show，系统换活动窗，拖动中断。

## 改动
- 新增 `ui_popup.make_passive_popup`：Tooltip 浮层标记已定位、摘掉 Map/Unmap 绑定、直接 alpha 1；`ui_widgets.Tooltip.show` 调用。
- 新增 `pet_cloud_move_guard.py`（`CloudMoveGuardMixin`）：`GetGUIThreadInfo` 检测 `GUI_INMOVESIZE`，自动显示排队、松手后用最新参数补显示，封顶约 48 秒；用户主动打开（focus=True）不拦；销毁路径收回定时器。
- `tests/test_popup_no_interrupt.py` 新增 7 条；`tests/test_tooltip.py` 的 `_Tip` 替身补 `unbind`/`attributes` 桩，**断言未动**。
- `_layers.py` 登记两个新模块；覆盖率基线刷新到 311 个模块，runbook 数字同步。

## 验证
- gui_hidden：popup_no_interrupt／tooltip／pet_cloud／ui_widgets／coverage_baseline 全绿；smoke_test 通过。
- architecture 仍红 6 项均非本轮引入：`ui_widgets.py` 1538>1500（合入 R1966 后 HEAD 已 1536）、`skill_panel.Panel` 973>972、test_agents_md／round_baselines／skill_reference_injection（worktree 缺基准历史、编号、00全流程SKILL 文件）。
- 未验证：真实指针下卡片显示/消失、真实拖窗不被打断，需用户在真实窗口确认。
