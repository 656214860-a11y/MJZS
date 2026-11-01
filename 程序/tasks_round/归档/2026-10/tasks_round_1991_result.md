# R1991 结果（修复轮）

## 用户反馈
软件放在副屏 2 时，「剧本准备 → 项目文件名」的悬停卡片和三虎弹出的聊天框都跳到主屏 1。

## 根因
两处都用 `winfo_screenwidth()` / `winfo_screenheight()` 当屏幕边界。这两个值永远是主屏尺寸，副屏上的坐标超出主屏宽度，被钳回主屏。
- `ui_widgets.Tooltip.show`：`x = min(x, 主屏宽 - 浮层宽)`。
- `pet_cloud_place._work_right` / `_screen_height`：取主屏尺寸；左边界、上边界默认当 0，副屏左侧起点也被算错。

## 改动
- `ui_popup.monitor_bounds(window, x=None, y=None)`：取鼠标点（或窗口）所在显示器的 `(left, top, right, bottom)`；非 Windows／接口不可用时退回 `(0, 0, 屏宽, 屏高)`，单屏行为不变。
- `Tooltip.show` 按鼠标所在显示器钳位，下沿放不下仍向上翻。
- `pet_cloud_place`：新增 `_monitor`／`_work_left`／`_work_top`，`_work_right`／`_screen_height` 改取主窗口所在显示器；`_inside_window`、`_room_above`、`_can_align_top`、`_avoid_pet`、`_origin` 的左／上边界由 `0`／`MARGIN` 改为 `显示器左／上 + MARGIN`。
- 新增 `tests/test_multi_monitor_popups.py`（6 条）：卡片留在副屏、副屏右边缘收回、副屏下沿上翻；聊天框留在副屏、不被钳到主屏宽度、不越副屏左边缘。

## 验证
- gui_hidden 定向：multi_monitor／tooltip／pet_cloud／popup／cell_menu／architecture 通过，新增 6 条全绿。断言未动。
- 仍红且与本轮无关：`test_pet_ui.CloudTests.test_the_cloud_stands_left_of_the_pet_with_its_bottom_lined_up`（隐藏桌面是竖屏主屏 1080×1920 + 右侧副屏，锚点 x=1200 在副屏而父窗口在主屏，旧代码结果相同）；DesktopPetSeam 5 条（登录态）；idea_chat 一批（worktree 缺 SKILL 文件）；`desktop.py::Desktop` 1303 > 1302、test_agents_md、test_round_baselines、test_skill_reference_injection（历史红）。
- 未验证：真实双屏下的实际观感，需用户确认。
