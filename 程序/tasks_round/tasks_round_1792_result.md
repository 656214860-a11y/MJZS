# 结果：微交互与动效优化（性能/资源轮）

## 三问

- **本轮类型**：性能/资源轮。纯 Tkinter＋标准库，无第三方动画库；不改业务逻辑与用户数据。
- **测试跑了吗**：窄测试均在本树真跑，全部通过：
  `test_ui_motion_perf`(26，连跑 3 次稳定)、`test_ui_motion`(15)、`test_ui_modern_system`(27)、`test_ui_style_engine`(13)、`test_ui_theme`(15)、`test_ui_widgets_inputs`(9)、`test_ui_widgets_table`(3)、`test_window_resize_coalescing`(7)、`test_ui_batch3_shell`(8)、`test_root_layout`(1)、`test_ui_batch6_pages`(7)、`test_desktop_compact_layout`(5)、`test_ui_edges -k wheel/scroll/mouse`(6)；
  架构门禁 `test_layers`、`test_token_boundary`、`test_module_size_ratchet`、`test_function_size_ratchet`、`test_ui_icons_boundary`、`test_no_circular_import`、`test_scrollbar_theme_boundary` 全绿；`smoke_test.py` 8/8。
  **未运行**：`test_ui_edges` 整体（上一轮基线对比无结论）、完整 `run_selftests`。
- **欠账**：未新增；`test_ui_edges` 整体基线对比仍是欠账。

## 改动（文件:函数）

- `ui_scroll.py`（新，L4）：`EasedScroll`／`eased_scroll(canvas, steps)`——滚轮推目标位置，每帧走剩余距离的 `SCROLL_EASE`（缓出）；首步在事件里同步走；连续滚轮累加；别处移动画布（翻页键、拖滚动条、代码定位）则放弃剩余动画；不可滚或设了 `yscrollincrement` 时退回原生；销毁取消定时器。
- `ui_hover_fade.py`（新，L4）：`install_hover_fade(root)`——对 `TButton` 类绑定 Enter/Leave；进出时临时切到派生样式 `Fade<k>.<原样式>`（混色圆角底图按需生成并缓存，保留按下／禁用两态），`HOVER_FADE_MS` 分 `HOVER_FADE_STEPS` 档，走完还原原样式；动画期间样式被别处改写、按钮被禁用或销毁则立即停，不覆盖别人写的样式。
- `ui_rounded.py`：`rounded_layout`（自 ui_widgets 迁入）、`button_specs`（圆角按钮规格登记）。
- `ui_widgets.py`：`_configure_button` 登记规格；`setup_styles` 调 `install_hover_fade`。
- `desktop_layout_resize.py:ResizeCoalescer`：新增可选 `freeze`／`thaw`；仅当探测**确认**光标捏着外框时冻结一次，松手后在补做重排**之前**解冻；`flush`／`cancel` 立即解冻；探测不到（降级路径）只合并、不冻结。
- `desktop_layout.py`：`watch_window_resize` 传入 `_freeze_content`／`_thaw_content`（页面内容与侧栏内容的画布窗口项 hidden／normal）；`scroll_page` 的页面与侧栏滚动改走 `eased_scroll`。
- `responsive_ui.py:ScrollForm.wheel`：改走 `eased_scroll`。
- `ui_tokens.py`：`SCROLL_EASE`／`SCROLL_FRAME_MS`／`SCROLL_SNAP_PX`、`HOVER_FADE_MS`／`HOVER_FADE_STEPS`。
- 文档与登记：`ui_components.md`（「动效与拖窗口」一节）、`architecture.md`、`PROJECT_MAP.md`、`tests/architecture/_layers.py`（`ui_scroll`、`ui_hover_fade` 登记 L4）。
- 新增测试：`tests/test_ui_motion_perf.py`。

## 实测数据

- **拖窗口每帧耗时**（本机，真实主窗口，模拟 24/16 帧连续改尺寸，`drag_active` 固定为真）：不冻结 353／431／517 ms，冻结 150／117／118 ms，约 3 倍。依据：Python 侧布局回调本身仅几毫秒（`fit_content` 110 次合计 3ms），耗时在原生绘制；旧的"拖动中不重排"此前已生效（拖动期间 Python 布局调用 0 次），本轮补的是不再绘制被遮的内容。
- **悬停渐变**：真窗口逐档读像素，进入 `#0f6fc0→#0e6bba→#0e67b3→#0d63ac` 后还原为原样式，离开反向；样式被别处改写时保持别人的写法。
- **滚动**：1 格 = 22px，与 Tk 原生 `yview_scroll(1,'units')` 一致；约 6 帧收敛。

## 变异验证

三处各做一次，对应用例变红，还原后 sha256 一致：A 去掉首步同步（4 红）；B 去掉补做前解冻（2 红）；C 动画期间不再检查样式是否被改写（2 红）。

## 「断言未动」声明

本轮未改、未弱化、未删除任何既有测试断言；`tests/architecture/_layers.py` 仅新增两个模块的层级登记。

## 已知限制与需裁决

1. 拖动外框时中间内容区与侧栏内容是空白的，松手后恢复；如认为空白闪烁难看，可改为只收起页面内容、保留侧栏（帧耗时回升）。
2. `Text`／`Treeview`／`Listbox` 内部滚动仍按行走，未做缓动。
3. 帧耗时数据来自模拟拖动（测试窗口无 OS 拖动节奏），不是真实鼠标拖拽实测。
4. 与 `claude/project-handoff-f6eb50` 的未合入提交在 `ui_widgets.py`／`responsive_ui.py`／`desktop.py` 附近会有合并冲突，需合并时处理。
